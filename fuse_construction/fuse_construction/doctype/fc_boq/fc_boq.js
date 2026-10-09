// FC BOQ — price it, submit it, award it, then raise what the job needs from it.

frappe.ui.form.on("FC BOQ", {
	setup(frm) {
		frm.set_query("project", () => ({ filters: { company: frm.doc.company, status: "Open" } }));
		frm.set_query("template", () => ({ filters: { disabled: 0 } }));
		frm.set_query("task", "client_release_stages", () => ({ filters: { project: frm.doc.project } }));
	},

	onload(frm) {
		// A new form arrives with every number at 0, so the server cannot tell "not set" from
		// "set to nothing". Fill the agreed defaults here, where the user can see and change them.
		if (!frm.is_new()) return;
		frappe.db.get_doc("FC Settings").then((s) => {
			const defaults = {
				markup_percent: s.boq_markup_percent,
				client_retention_percent: s.client_retention_percent,
				client_retention_cap_percent: s.client_retention_cap_percent,
				client_advance_percent: s.client_advance_percent,
				dlp_months: s.dlp_months,
				payment_terms_days: s.payment_terms_days,
			};
			Object.keys(defaults).forEach((field) => {
				if (!flt(frm.doc[field]) && flt(defaults[field])) frm.set_value(field, defaults[field]);
			});
			if (!frm.doc.company && s.default_company) frm.set_value("company", s.default_company);
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.template) {
			frm.add_custom_button(__("Apply Template"), () => apply_template(frm));
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Submitted") {
			frm.add_custom_button(__("Award"), () => award(frm)).addClass("btn-primary");
		}

		if (frm.doc.status === "Awarded") {
			const create = __("Create");
			frm.add_custom_button(__("Tender"), () => make_tender(frm), create);
			frm.add_custom_button(__("Subcontract"), () => make_subcontract(frm), create);
			frm.add_custom_button(__("Material Request"), () => call_and_open(frm,
				"fuse_construction.commercial.make_material_request", { boq: frm.doc.name }, "Material Request"), create);
			if (frm.doc.contract_model === "EPC") {
				frm.add_custom_button(__("Client Valuation"), () => frappe.new_doc("FC Client Valuation", { boq: frm.doc.name }), create);
				frm.add_custom_button(__("Client Retention Release"), () =>
					frappe.new_doc("FC Retention Release", { release_for: "Client", boq: frm.doc.name }), create);
			}
			frm.add_custom_button(__("Budget Revision"), () =>
				frappe.new_doc("FC Budget Revision", { project: frm.doc.project }), create);

			const view = __("View");
			frm.add_custom_button(__("Project"), () => frappe.set_route("Form", "Project", frm.doc.project), view);
			frm.add_custom_button(__("Project Shape"), () =>
				frappe.set_route("query-report", "FC Project Shape", { project: frm.doc.project }), view);
			frm.add_custom_button(__("Dashboard"), () =>
				frappe.set_route("fc-project-dashboard", { project: frm.doc.project }), view);
		}

		if (frm.doc.docstatus === 1 && frm.doc.contract_model === "EPC" && !frm.doc.quotation) {
			frm.add_custom_button(__("Quotation"), () => make_quotation(frm), __("Create"));
		}
	},

	capacity_kwp(frm) {
		resize_hint(frm);
	},
	storage_kwh(frm) {
		resize_hint(frm);
	},
	markup_percent(frm) {
		frm.doc.items.forEach((row) => price_row(frm, row.doctype, row.name));
	},
});

frappe.ui.form.on("FC BOQ Item", {
	qty: price_row,
	rate: price_row,
	labour_rate: price_row,
	plant_rate: price_row,
	material_rate: price_row,
	subcontract_rate: price_row,
});

// A preview while typing. The server prices the BOQ again on save, and its figures win.
function price_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const built = ["labour_rate", "plant_rate", "material_rate", "subcontract_rate"]
		.reduce((sum, field) => sum + flt(row[field]), 0);
	if (built) frappe.model.set_value(cdt, cdn, "rate", built);
	const amount = flt(flt(row.qty) * flt(built || row.rate), 2);
	frappe.model.set_value(cdt, cdn, "amount", amount);
	frappe.model.set_value(cdt, cdn, "sell_amount", flt(amount * (1 + flt(frm.doc.markup_percent) / 100), 2));
}

function resize_hint(frm) {
	if (frm.doc.docstatus === 0 && frm.doc.template && (frm.doc.items || []).length) {
		frappe.show_alert({ message: __("Press Apply Template to re-size the lines to this plant."), indicator: "blue" });
	}
}

function apply_template(frm) {
	const go = () => frm.call("apply_template").then(() => {
		frm.dirty();
		frm.refresh_fields();
		frappe.show_alert({ message: __("Lines sized from {0}", [frm.doc.template]), indicator: "green" });
	});
	if ((frm.doc.items || []).length) {
		frappe.confirm(__("Replace every line with the template's, sized to {0} kWp and {1} kWh?",
			[flt(frm.doc.capacity_kwp), flt(frm.doc.storage_kwh)]), go);
	} else {
		go();
	}
}

function award(frm) {
	const into = frm.doc.project ? __("into project {0}", [frm.doc.project]) : __("as a new project");
	frappe.confirm(
		__("Award {0} {1}? A task opens for each section and the cost becomes the job's budget.", [frm.doc.name, into]),
		() => frm.call("award").then((r) => {
			frm.reload_doc();
			if (r.message) {
				frappe.msgprint({
					title: __("Awarded"),
					indicator: "green",
					message: __("Project {0} is open with {1} sections. Budget: {2}.", [
						`<a href="/app/project/${encodeURIComponent(r.message.project)}">${frappe.utils.escape_html(r.message.project)}</a>`,
						r.message.tasks,
						`<a href="/app/fc-project-budget/${encodeURIComponent(r.message.budget)}">${frappe.utils.escape_html(r.message.budget)}</a>`,
					]),
				});
			}
		})
	);
}

function sections(frm) {
	return (frm.doc.sections || []).map((row) => row.boq_group);
}

function make_tender(frm) {
	frappe.prompt(
		[
			{ fieldname: "boq_group", fieldtype: "Select", label: __("Section"), options: sections(frm), reqd: 1 },
			{ fieldname: "package_type", fieldtype: "Select", label: __("Package"), options: ["Subcontract", "Supply"], default: "Subcontract" },
		],
		(values) => call_and_open(frm, "fuse_construction.commercial.make_tender",
			{ boq: frm.doc.name, boq_group: values.boq_group, package_type: values.package_type }, "FC Tender"),
		__("Tender a package"),
		__("Create")
	);
}

function make_subcontract(frm) {
	frappe.prompt(
		[
			{ fieldname: "boq_group", fieldtype: "Select", label: __("Section"), options: sections(frm), reqd: 1 },
			{ fieldname: "supplier", fieldtype: "Link", label: __("Subcontractor"), options: "Supplier", reqd: 1 },
		],
		(values) => call_and_open(frm, "fuse_construction.commercial.make_subcontract",
			{ boq: frm.doc.name, boq_group: values.boq_group, supplier: values.supplier }, "FC Subcontract"),
		__("Subcontract a section directly"),
		__("Create")
	);
}

function make_quotation(frm) {
	frappe.prompt(
		[{ fieldname: "by", fieldtype: "Select", label: __("Price"), options: ["Section", "Lump Sum"], default: "Section" }],
		(values) => call_and_open(frm, "fuse_construction.commercial.make_quotation",
			{ boq: frm.doc.name, by: values.by }, "Quotation"),
		__("Quotation for the client"),
		__("Create")
	);
}

function call_and_open(frm, method, args, doctype) {
	frappe.call({ method, args, freeze: true }).then((r) => {
		if (r.message) frappe.set_route("Form", doctype, r.message);
	});
}
