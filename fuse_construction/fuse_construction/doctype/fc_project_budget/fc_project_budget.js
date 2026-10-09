// FC Project Budget — a snapshot. Every figure is the cost engine's; nothing here is typed.

frappe.ui.form.on("FC Project Budget", {
	refresh(frm) {
		frm.disable_save();
		if (frm.is_new()) return;
		frm.add_custom_button(__("Refresh Now"), () =>
			frm.call("refresh").then(() => frm.reload_doc())).addClass("btn-primary");
		frm.add_custom_button(__("Project Shape"), () =>
			frappe.set_route("query-report", "FC Project Shape", { project: frm.doc.project }), __("View"));
		frm.add_custom_button(__("Dashboard"), () =>
			frappe.set_route("fc-project-dashboard", { project: frm.doc.project }), __("View"));
		frm.add_custom_button(__("Budget Revision"), () =>
			frappe.new_doc("FC Budget Revision", { project: frm.doc.project }), __("Create"));

		const colour = { Green: "green", Amber: "orange", Red: "red" }[frm.doc.health];
		if (colour) frm.page.set_indicator(__(frm.doc.health), colour);
	},
});
