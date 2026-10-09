// Project form: the way into a construction job's BOQ, Project Shape and dashboard.
// Shown only on projects a BOQ was awarded to; every other project is untouched.

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.fc_boq) return;
		const group = __("Construction");
		frm.add_custom_button(__("BOQ"), () => frappe.set_route("Form", "FC BOQ", frm.doc.fc_boq), group);
		frm.add_custom_button(__("Project Shape"), () =>
			frappe.set_route("query-report", "FC Project Shape", { project: frm.doc.name }), group);
		frm.add_custom_button(__("Dashboard"), () =>
			frappe.set_route("fc-project-dashboard", { project: frm.doc.name }), group);
		frm.add_custom_button(__("Subcontracts"), () =>
			frappe.set_route("List", "FC Subcontract", { project: frm.doc.name }), group);
	},
});
