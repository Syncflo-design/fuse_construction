frappe.query_reports["FC Subcontract Status"] = {
	filters: [
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "supplier", label: __("Subcontractor"), fieldtype: "Link", options: "Supplier" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Active", "Practically Complete", "Closed"],
		},
	],
};
