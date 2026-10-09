// FC Subcontract Certificate — enter work done TO DATE; the server works out the rest.

frappe.ui.form.on("FC Subcontract Certificate", {
	setup(frm) {
		frm.set_query("subcontract", () => ({ filters: { docstatus: 1, status: ["in", ["Active", "Practically Complete"]] } }));
	},

	refresh(frm) {
		// With the approval workflow on, release is one of its actions. Without it, finance
		// releases from here.
		if (frm.doc.docstatus === 1 && frm.doc.approval_state === "Approved" && !frappe.model.has_workflow(frm.doctype)
			&& (frappe.user.has_role("Accounts Manager") || frappe.user.has_role("System Manager"))) {
			frm.add_custom_button(__("Release for Payment"), () =>
				frm.call("release").then(() => frm.reload_doc())).addClass("btn-primary");
		}
		if (frm.doc.docstatus === 1 && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Preview Intacct Posting"), () =>
				frappe.xcall("fuse_construction.intacct.posting.preview_posting", { doctype: frm.doctype, name: frm.doc.name })
					.then((xml) => frappe.msgprint({ title: __("What would be sent"), message: `<pre>${frappe.utils.escape_html(xml)}</pre>`, wide: true })),
				__("View"));
		}
	},

	subcontract(frm) {
		load_lines(frm);
	},
	certificate_type(frm) {
		frm.clear_table("lines");
		frm.clear_table("contra_charges");
		frm.refresh_fields();
		load_lines(frm);
	},
});

frappe.ui.form.on("FC Certificate Line", {
	to_date_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (flt(row.contract_qty)) {
			frappe.model.set_value(cdt, cdn, "to_date_percent", flt(flt(row.to_date_qty) / flt(row.contract_qty) * 100, 4));
		}
		preview(cdt, cdn);
	},
	to_date_percent(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const qty = flt(flt(row.contract_qty) * flt(row.to_date_percent) / 100, 3);
		if (Math.abs(qty - flt(row.to_date_qty)) > 0.0005) frappe.model.set_value(cdt, cdn, "to_date_qty", qty);
		preview(cdt, cdn);
	},
});

// A preview while typing. Retention, advance recovery and the net are the server's, on save.
function preview(cdt, cdn) {
	const row = locals[cdt][cdn];
	const to_date = flt(flt(row.to_date_qty) * flt(row.rate), 2);
	frappe.model.set_value(cdt, cdn, "to_date_amount", to_date);
	frappe.model.set_value(cdt, cdn, "this_amount", flt(to_date - flt(row.previous_amount), 2));
}

function load_lines(frm) {
	if (!frm.doc.subcontract || frm.doc.certificate_type !== "Progress" || (frm.doc.lines || []).length) return;
	frappe.xcall("fuse_construction.fuse_construction.doctype.fc_subcontract_certificate.fc_subcontract_certificate.certificate_lines",
		{ subcontract: frm.doc.subcontract }).then((r) => {
		frm.clear_table("lines");
		r.lines.forEach((line) => frm.add_child("lines", line));
		frm.refresh_field("lines");
		if (r.has_advance_due) {
			frappe.show_alert({ message: __("The advance on this subcontract has not been paid yet."), indicator: "orange" });
		}
	});
}
