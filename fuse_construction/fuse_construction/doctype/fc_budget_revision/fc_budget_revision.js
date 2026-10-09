// FC Budget Revision — start from every section's current budget and change what moves.

frappe.ui.form.on("FC Budget Revision", {
	setup(frm) {
		frm.set_query("project", () => ({ filters: { fc_boq: ["is", "set"] } }));
	},

	project(frm) {
		if (!frm.doc.project || (frm.doc.lines || []).length) return;
		frappe.xcall("fuse_construction.fuse_construction.doctype.fc_budget_revision.fc_budget_revision.revision_lines",
			{ project: frm.doc.project }).then((rows) => {
			frm.clear_table("lines");
			rows.forEach((row) => frm.add_child("lines", row));
			frm.refresh_field("lines");
		});
	},

	before_save(frm) {
		// Untouched sections are noise on an approval; keep only what changes.
		const moving = (frm.doc.lines || []).filter((row) => flt(row.change) !== 0);
		if (moving.length && moving.length !== frm.doc.lines.length) {
			frm.doc.lines = moving;
			moving.forEach((row, i) => (row.idx = i + 1));
		}
	},
});

frappe.ui.form.on("FC Budget Revision Line", {
	change(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "new_budget", flt(flt(row.current_budget) + flt(row.change), 2));
		frm.set_value("total_change", flt((frm.doc.lines || []).reduce((sum, r) => sum + flt(r.change), 0), 2));
	},
});
