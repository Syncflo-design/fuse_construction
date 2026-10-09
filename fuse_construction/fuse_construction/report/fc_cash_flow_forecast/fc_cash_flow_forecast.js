frappe.query_reports["FC Cash Flow Forecast"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Month"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{ fieldname: "months", label: __("Months"), fieldtype: "Int", default: 6, reqd: 1 },
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && ["net", "cumulative"].includes(column.fieldname) && flt(data[column.fieldname]) < 0) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
