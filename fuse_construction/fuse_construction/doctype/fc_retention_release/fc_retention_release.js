// FC Retention Release — pick the stage; the amount is worked out from what is held.

const FCRR_METHOD = "fuse_construction.fuse_construction.doctype.fc_retention_release.fc_retention_release.open_stages";

frappe.ui.form.on("FC Retention Release", {
	setup(frm) {
		frm.set_query("subcontract", () => ({ filters: { docstatus: 1, retention_outstanding: [">", 0] } }));
		frm.set_query("boq", () => ({ filters: { status: "Awarded", contract_model: "EPC" } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && (frm.doc.subcontract || frm.doc.boq)) {
			frm.add_custom_button(__("Choose Stage"), () => choose_stage(frm));
		}
		if (frm.doc.docstatus === 1 && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Preview Intacct Posting"), () =>
				frappe.xcall("fuse_construction.intacct.posting.preview_posting", { doctype: frm.doctype, name: frm.doc.name })
					.then((xml) => frappe.msgprint({ title: __("What would be sent"), message: `<pre>${frappe.utils.escape_html(xml)}</pre>`, wide: true })),
				__("View"));
		}
	},

	subcontract(frm) {
		frm.set_value("stage", "");
		if (frm.doc.subcontract) choose_stage(frm, true);
	},
	boq(frm) {
		frm.set_value("stage", "");
		if (frm.doc.boq) choose_stage(frm, true);
	},
});

function choose_stage(frm, quiet) {
	const name = frm.doc.release_for === "Client" ? frm.doc.boq : frm.doc.subcontract;
	if (!name) return;
	frappe.xcall(FCRR_METHOD, { release_for: frm.doc.release_for, name }).then((stages) => {
		if (!stages.length) {
			frappe.msgprint(__("Every release stage has already been released."));
			return;
		}
		if (stages.length === 1 && quiet) {
			frm.set_value("stage", stages[0].name);
			return;
		}
		frappe.prompt(
			[{
				fieldname: "stage",
				fieldtype: "Select",
				label: __("Release stage"),
				reqd: 1,
				options: stages.map((s) => ({
					value: s.name,
					label: `${s.stage_name} — ${s.share_percent}%` + (s.due_date ? ` · ${__("due")} ${frappe.datetime.str_to_user(s.due_date)}` : ""),
				})),
				default: stages[0].name,
			}],
			(values) => {
				frm.set_value("stage", values.stage);
				frm.save();
			},
			__("Which stage?"),
			__("Choose")
		);
	});
}
