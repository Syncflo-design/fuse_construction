frappe.query_reports["FC Tender Summary"] = {
	filters: [
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Published", "Under Evaluation", "Awarded", "Cancelled"],
		},
		{ fieldname: "package_type", label: __("Type"), fieldtype: "Select", options: ["", "Subcontract", "Supply"] },
		{ fieldname: "from_date", label: __("Deadline From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Deadline To"), fieldtype: "Date" },
	],
};
