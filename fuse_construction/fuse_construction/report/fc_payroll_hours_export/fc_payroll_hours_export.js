frappe.query_reports["FC Payroll Hours Export"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Period From"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{ fieldname: "to_date", label: __("Period To"), fieldtype: "Date", default: frappe.datetime.month_end(), reqd: 1 },
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "worker_type",
			label: __("Worker Type"),
			fieldtype: "Select",
			options: ["", "Employee", "Labour Broker", "Subcontractor Labour"],
		},
	],
};
