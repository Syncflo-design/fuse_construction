// FC Tender — publish, record bids, evaluate, award.

frappe.ui.form.on("FC Tender", {
	setup(frm) {
		frm.set_query("boq", () => ({ filters: { docstatus: 1 } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.status === "Published") {
			frm.add_custom_button(__("Start Evaluation"), () =>
				frappe.xcall("fuse_construction.commercial.set_tender_status", { tender: frm.doc.name, status: "Under Evaluation" })
					.then(() => frm.reload_doc()));
		}
		if (["Published", "Under Evaluation"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Award"), () => award(frm)).addClass("btn-primary");
		}
		if (frm.doc.subcontract) {
			frm.add_custom_button(__("Subcontract"), () => frappe.set_route("Form", "FC Subcontract", frm.doc.subcontract), __("View"));
		}
		if (frm.doc.purchase_order) {
			frm.add_custom_button(__("Purchase Order"), () => frappe.set_route("Form", "Purchase Order", frm.doc.purchase_order), __("View"));
		}
	},
});

frappe.ui.form.on("FC Tender Item", {
	qty: amount,
	estimated_rate: amount,
});

function amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "estimated_amount", flt(flt(row.qty) * flt(row.estimated_rate), 2));
}

function award(frm) {
	const bids = (frm.doc.bidders || []).filter((b) => flt(b.bid_amount) > 0 && b.bid_status !== "Declined");
	if (!bids.length) {
		frappe.msgprint(__("Record at least one bid first."));
		return;
	}
	bids.sort((a, b) => flt(a.bid_amount) - flt(b.bid_amount));
	frappe.prompt(
		[{
			fieldname: "supplier",
			fieldtype: "Select",
			label: __("Award to"),
			reqd: 1,
			options: bids.map((b) => ({
				value: b.supplier,
				label: `${b.supplier_name || b.supplier} — ${format_currency(b.bid_amount)}` +
					(b.technically_compliant ? "" : ` (${__("not marked compliant")})`),
			})),
			default: frm.doc.lowest_bidder || bids[0].supplier,
		}],
		(values) => frappe.call({
			method: "fuse_construction.commercial.award_tender",
			args: { tender: frm.doc.name, supplier: values.supplier },
			freeze: true,
		}).then((r) => {
			if (r.message) frappe.set_route("Form", r.message.doctype, r.message.name);
		}),
		__("Award the tender"),
		__("Award")
	);
}
