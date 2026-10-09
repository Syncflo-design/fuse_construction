// FC Crew Timesheet — the desk view of what the Site screen books.

frappe.ui.form.on("FC Crew Timesheet", {
	setup(frm) {
		frm.set_query("task", () => ({ filters: { project: frm.doc.project } }));
		frm.set_query("task", "rows", () => ({ filters: { project: frm.doc.project } }));
		frm.set_query("employee", "rows", () => ({ filters: { status: "Active" } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.is_new()) return;
		if (["Draft", "Returned"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Send for Approval"), () =>
				frappe.xcall("fuse_construction.labour.submit_for_approval", { name: frm.doc.name }).then(() => frm.reload_doc())
			).addClass("btn-primary");
		}
		if (frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("Approve"), () =>
				frappe.call({ method: "fuse_construction.labour.approve", args: { name: frm.doc.name }, freeze: true })
					.then(() => frm.reload_doc())
			).addClass("btn-primary");
			frm.add_custom_button(__("Send Back"), () => frappe.prompt(
				[{ fieldname: "reason", fieldtype: "Small Text", label: __("What needs fixing?"), reqd: 1 }],
				(values) => frappe.xcall("fuse_construction.labour.send_back", { name: frm.doc.name, reason: values.reason })
					.then(() => frm.reload_doc()),
				__("Send back"),
				__("Send back")
			));
		}
	},
});
