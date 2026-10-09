frappe.query_reports["FC Crew Hours"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			reqd: 1,
		},
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "employee", label: __("Worker"), fieldtype: "Link", options: "Employee" },
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: ["Worker", "Section", "Project", "Day", "Detail"],
			default: "Worker",
		},
		{ fieldname: "include_pending", label: __("Include Pending"), fieldtype: "Check" },
	],
};
