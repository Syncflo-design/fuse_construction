frappe.query_reports["FC BOQ Summary"] = {
	filters: [
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "customer", label: __("Client"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Submitted", "Awarded", "Cancelled"],
		},
		{ fieldname: "contract_model", label: __("Model"), fieldtype: "Select", options: ["", "EPC", "IPP"] },
	],
};
