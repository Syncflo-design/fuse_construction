// The construction demo loader sits on the BOQ list, for the person setting the demo profile up.
// System Manager only. Everything it makes stays in Fuse — no Intacct call.

frappe.listview_settings["FC BOQ"] = {
	add_fields: ["status", "contract_model"],
	get_indicator(doc) {
		const colour = { Draft: "red", Submitted: "blue", Awarded: "green", Cancelled: "grey" }[doc.status] || "grey";
		return [__(doc.status), colour, "status,=," + doc.status];
	},
	onload(listview) {
		if (!frappe.user.has_role("System Manager")) return;
		listview.page.add_menu_item(__("Load Construction Demo"), () => {
			frappe.confirm(
				__("Load the construction demo: a C&I solar + BESS template, a 6.5 MWp + 7 MWh job awarded from it, crews, subcontractors and a civils tender with three bids. Nothing goes to Intacct."),
				() => frappe.call({
					method: "fuse_construction.demo.nse.load",
					freeze: true,
					freeze_message: __("Loading the construction demo..."),
				}).then((r) => {
					if (!r.message) return;
					frappe.msgprint({ title: __("Construction demo loaded"), indicator: "green", message: r.message.summary });
					frappe.set_route("Form", "FC BOQ", r.message.boq);
				})
			);
		});
	},
};
