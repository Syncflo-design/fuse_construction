// FC Client Valuation — % complete to date per section, or the milestones reached.

const FCV_METHOD = "fuse_construction.fuse_construction.doctype.fc_client_valuation.fc_client_valuation.valuation_rows";

frappe.ui.form.on("FC Client Valuation", {
	setup(frm) {
		frm.set_query("boq", () => ({ filters: { status: "Awarded", contract_model: "EPC", docstatus: 1 } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Preview Intacct Posting"), () =>
				frappe.xcall("fuse_construction.intacct.posting.preview_posting", { doctype: frm.doctype, name: frm.doc.name })
					.then((xml) => frappe.msgprint({ title: __("What would be sent"), message: `<pre>${frappe.utils.escape_html(xml)}</pre>`, wide: true })),
				__("View"));
		}
	},

	boq(frm) {
		load(frm);
	},
	valuation_type(frm) {
		frm.clear_table("lines");
		frm.clear_table("milestone_lines");
		frm.refresh_fields();
		load(frm);
	},
});

frappe.ui.form.on("FC Valuation Line", {
	percent_complete(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const to_date = flt(flt(row.contract_value) * flt(row.percent_complete) / 100, 2);
		frappe.model.set_value(cdt, cdn, "value_to_date", to_date);
		frappe.model.set_value(cdt, cdn, "this_value",
			flt(to_date - flt(row.contract_value) * flt(row.previous_percent) / 100, 2));
	},
});

function load(frm) {
	if (!frm.doc.boq || frm.doc.valuation_type === "Advance") return;
	const table = frm.doc.valuation_type === "Milestone" ? "milestone_lines" : "lines";
	if ((frm.doc[table] || []).length) return;
	frappe.xcall(FCV_METHOD, { boq: frm.doc.boq, valuation_type: frm.doc.valuation_type }).then((rows) => {
		frm.clear_table(table);
		rows.forEach((row) => frm.add_child(table, row));
		frm.refresh_field(table);
	});
}
