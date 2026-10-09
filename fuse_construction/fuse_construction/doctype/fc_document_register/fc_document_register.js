// FC Document Register — who it is from and to is a supplier, client, employee or us.

const FCDR_PARTIES = ["Supplier", "Customer", "Employee", "Company"];

frappe.ui.form.on("FC Document Register", {
	setup(frm) {
		["originator_type", "recipient_type"].forEach((field) =>
			frm.set_query(field, () => ({ filters: { name: ["in", FCDR_PARTIES] } })));
		frm.set_query("boq_group", () => ({}));
	},
});
