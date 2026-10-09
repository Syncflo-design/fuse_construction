frappe.query_reports["FC Retention Ledger"] = {
	filters: [
		{
			fieldname: "direction",
			label: __("Held From"),
			fieldtype: "Select",
			options: ["Both", "Subcontractors", "Clients"],
			default: "Both",
		},
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "supplier", label: __("Subcontractor"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "customer", label: __("Client"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "show_empty", label: __("Include Contracts with Nothing Held"), fieldtype: "Check" },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "next_status") {
			const colour = { Due: "red", Pending: "blue", Released: "green" }[data.next_status] || "grey";
			value = `<span class="indicator-pill ${colour}">${frappe.utils.escape_html(data.next_status || "")}</span>`;
		}
		if (data && column.fieldname === "next_due" && data.overdue) {
			value = `<span style="color: var(--red-600)"><b>${value}</b></span>`;
		}
		return value;
	},
};
