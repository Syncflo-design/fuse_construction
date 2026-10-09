// FC Subcontract — terms, schedule, and everything raised against it.

frappe.ui.form.on("FC Subcontract", {
	setup(frm) {
		frm.set_query("boq", () => ({ filters: { status: "Awarded", project: frm.doc.project || undefined } }));
		frm.set_query("task", "release_stages", () => ({ filters: { project: frm.doc.project } }));
		frm.set_query("task", "payment_schedule", () => ({ filters: { project: frm.doc.project } }));
	},

	onload(frm) {
		// A new form arrives with every number at 0; fill the agreed terms where they can be seen.
		if (!frm.is_new()) return;
		frappe.db.get_doc("FC Settings").then((s) => {
			const defaults = {
				retention_percent: s.sub_retention_percent,
				retention_cap_percent: s.sub_retention_cap_percent,
				advance_percent: s.sub_advance_percent,
				advance_recovery_percent: s.sub_advance_recovery_percent,
				payment_terms_days: s.payment_terms_days,
				dlp_months: s.dlp_months,
			};
			Object.keys(defaults).forEach((field) => {
				if (!flt(frm.doc[field]) && flt(defaults[field])) frm.set_value(field, defaults[field]);
			});
			if (!frm.doc.company && s.default_company) frm.set_value("company", s.default_company);
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Generate Payment Schedule"), () =>
				frm.call("generate_schedule").then(() => { frm.dirty(); frm.refresh_fields(); }));
		}
		if (frm.doc.docstatus !== 1 || ["Closed", "Cancelled"].includes(frm.doc.status)) return;

		const create = __("Create");
		frm.add_custom_button(__("Progress Certificate"), () =>
			frappe.new_doc("FC Subcontract Certificate", { subcontract: frm.doc.name, certificate_type: "Progress" }), create);
		if (flt(frm.doc.advance_amount) > flt(frm.doc.advance_paid)) {
			frm.add_custom_button(__("Advance Payment"), () =>
				frappe.new_doc("FC Subcontract Certificate", { subcontract: frm.doc.name, certificate_type: "Advance Payment" }), create);
		}
		if (flt(frm.doc.retention_outstanding) > 0) {
			frm.add_custom_button(__("Retention Release"), () =>
				frappe.new_doc("FC Retention Release", { release_for: "Subcontractor", subcontract: frm.doc.name }), create);
		}

		if (!frm.doc.practical_completion_date) {
			frm.add_custom_button(__("Practical Completion"), () => frappe.prompt(
				[{ fieldname: "date", fieldtype: "Date", label: __("Practically complete on"), default: frappe.datetime.get_today(), reqd: 1 }],
				(values) => frm.call("set_practical_completion", { date: values.date }).then(() => frm.reload_doc()),
				__("Practical completion"),
				__("Record")
			));
		}
		if (flt(frm.doc.retention_outstanding) <= 0 && flt(frm.doc.certified_to_date) > 0) {
			frm.add_custom_button(__("Close (Final Account)"), () => frappe.confirm(
				__("Close {0}? Nothing more will be committed on it.", [frm.doc.name]),
				() => frm.call("close").then(() => frm.reload_doc())
			));
		}
		if (frm.doc.purchase_order) {
			frm.add_custom_button(__("Purchase Order"), () => frappe.set_route("Form", "Purchase Order", frm.doc.purchase_order), __("View"));
		}
		frm.add_custom_button(__("Certificates"), () =>
			frappe.set_route("List", "FC Subcontract Certificate", { subcontract: frm.doc.name }), __("View"));
	},

	advance_percent(frm) {
		if (flt(frm.doc.advance_percent)) {
			frm.set_value("advance_amount", flt(frm.doc.subcontract_value * frm.doc.advance_percent / 100, 2));
		}
	},
});

frappe.ui.form.on("FC Subcontract Line", {
	qty: price_line,
	rate: price_line,
	lines_remove(frm) {
		total(frm);
	},
});

function price_line(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(flt(row.qty) * flt(row.rate), 2));
	total(frm);
}

function total(frm) {
	frm.set_value("subcontract_value", flt((frm.doc.lines || []).reduce((sum, row) => sum + flt(row.amount), 0), 2));
}
