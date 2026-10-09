"""Site configuration this app owns: custom fields, seed lists, the certificate workflow and
the Construction workspace.

Wired to after_install AND after_migrate, and exposed as fuse_construction.api.setup,
because after_migrate has been seen not to fire on a Frappe Cloud deploy. Everything here is
idempotent: a second run only closes gaps, and nothing a client has changed is overwritten
(seed lists are only seeded when empty; the workflow only created when absent).

Custom fields are all `fc_` and only ADD to ERPNext documents. No ERPNext or Fuse doctype has
a field changed or removed, and no Fuse Manufacturing or Fuse Projects doctype is touched.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from fuse_construction import registry, settings

SECTION_LINK = {"fieldtype": "Link", "options": "Task", "label": "BOQ Section"}

CUSTOM_FIELDS = {
	"Purchase Order": [
		{"fieldname": "fc_subcontract", "fieldtype": "Link", "options": "FC Subcontract", "label": "Subcontract",
			"insert_after": "schedule_date", "read_only": 1, "no_copy": 1, "allow_on_submit": 1,
			"description": "Raised by this subcontract. The cost report counts the subcontract, not this order."},
		{"fieldname": "fc_boq", "fieldtype": "Link", "options": "FC BOQ", "label": "BOQ",
			"insert_after": "fc_subcontract", "read_only": 1, "no_copy": 1},
	],
	# The section a line is bought for. The project says which job; the section is where the
	# cost report puts the commitment and the receipt. Copied down the chain by ERPNext's own
	# mapping (same field name on every line): request → order → receipt.
	"Material Request Item": [dict(SECTION_LINK, fieldname="fc_task", insert_after="project")],
	"Purchase Order Item": [dict(SECTION_LINK, fieldname="fc_task", insert_after="project")],
	"Purchase Receipt Item": [dict(SECTION_LINK, fieldname="fc_task", insert_after="project")],
	"Stock Entry Detail": [dict(SECTION_LINK, fieldname="fc_task", insert_after="project")],
	"Timesheet": [
		{"fieldname": "fc_crew_timesheet", "fieldtype": "Link", "options": "FC Crew Timesheet",
			"label": "Crew Timesheet", "insert_after": "company", "read_only": 1, "no_copy": 1},
	],
	"Task": [
		{"fieldname": "fc_boq", "fieldtype": "Link", "options": "FC BOQ", "label": "BOQ",
			"insert_after": "project", "read_only": 1, "no_copy": 1},
		{"fieldname": "fc_boq_group", "fieldtype": "Link", "options": "FC BOQ Group", "label": "BOQ Section",
			"insert_after": "fc_boq", "read_only": 1, "no_copy": 1, "in_standard_filter": 1},
	],
	"Project": [
		{"fieldname": "fc_boq", "fieldtype": "Link", "options": "FC BOQ", "label": "BOQ",
			"insert_after": "project_name", "read_only": 1, "no_copy": 1},
	],
	"Quotation": [
		{"fieldname": "fc_boq", "fieldtype": "Link", "options": "FC BOQ", "label": "BOQ",
			"insert_after": "party_name", "read_only": 1, "no_copy": 1},
	],
	# Who a worker is matters for payroll and for who pays them. Labour-broker staff are
	# Employees flagged here, so a crew can be booked the same way whoever employs them.
	"Employee": [
		{"fieldname": "fc_worker_type", "fieldtype": "Select", "label": "Worker Type",
			"options": "\nEmployee\nLabour Broker\nSubcontractor Labour", "insert_after": "designation"},
		{"fieldname": "fc_trade", "fieldtype": "Link", "options": "Activity Type", "label": "Trade",
			"insert_after": "fc_worker_type",
			"description": "The activity this worker's time is booked as by default."},
		{"fieldname": "fc_labour_broker", "fieldtype": "Link", "options": "Supplier", "label": "Labour Broker",
			"insert_after": "fc_trade", "depends_on": "eval:doc.fc_worker_type=='Labour Broker'"},
	],
}

# Only on a site with Frappe CRM. The deal carries what a won job needs to open itself.
CRM_FIELDS = {
	"CRM Deal": [
		{"fieldname": "fc_section", "fieldtype": "Section Break", "label": "Construction"},
		{"fieldname": "fc_template", "fieldtype": "Link", "options": "FC BOQ Template", "label": "BOQ Template",
			"insert_after": "fc_section"},
		{"fieldname": "fc_contract_model", "fieldtype": "Select", "options": "EPC\nIPP", "default": "EPC",
			"label": "Model", "insert_after": "fc_template"},
		{"fieldname": "fc_capacity_kwp", "fieldtype": "Float", "label": "PV Capacity (kWp)",
			"insert_after": "fc_contract_model"},
		{"fieldname": "fc_storage_kwh", "fieldtype": "Float", "label": "Storage (kWh)",
			"insert_after": "fc_capacity_kwp"},
		{"fieldname": "fc_boq", "fieldtype": "Link", "options": "FC BOQ", "label": "BOQ",
			"insert_after": "fc_storage_kwh", "read_only": 1, "no_copy": 1},
		{"fieldname": "fc_project", "fieldtype": "Link", "options": "Project", "label": "Project",
			"insert_after": "fc_boq", "read_only": 1, "no_copy": 1},
	],
}

COST_HEADS = [
	("Materials", "Material"),
	("Labour", "Labour"),
	("Plant and Equipment", "Plant"),
	("Subcontract", "Subcontract"),
	("Preliminaries and General", "Overhead"),
	("Overheads", "Overhead"),
	("Contingency", "Overhead"),
]

# Solar PV + battery storage, as NSE builds it. A client adds their own; these are only
# seeded on a site that has none.
BOQ_GROUPS = [
	("Preliminaries and General", "Design", "PG"),
	("Engineering and Design", "Design", "ENG"),
	("Civils and Earthworks", "Construction", "CIV"),
	("Mounting Structures", "Construction", "MNT"),
	("PV Modules", "Procurement", "PVM"),
	("Inverters", "Procurement", "INV"),
	("Battery Storage (BESS)", "Procurement", "BES"),
	("DC and AC Cabling", "Construction", "CAB"),
	("MV Grid Connection", "Construction", "MV"),
	("Commissioning", "Commissioning", "COM"),
]

WORKFLOW = "FC Subcontract Certificate Approval"


def after_install():
	"""Put this app's configuration in step with this version of it."""
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	crm = False
	if frappe.db.exists("DocType", "CRM Deal"):
		create_custom_fields(CRM_FIELDS, ignore_validate=True)
		crm = True
	seeded = {
		"cost_heads": _seed_tree("FC Cost Head", "cost_head_name", [(n, {"item_type": t}) for n, t in COST_HEADS]),
		"boq_groups": _seed_tree(
			"FC BOQ Group", "boq_group_name",
			[(n, {"phase": p, "cost_code_prefix": c}) for n, p, c in BOQ_GROUPS],
		),
	}
	_settings_defaults()
	workflow = _workflow()
	workspace = build_workspace()
	switches = _sync_switches()
	frappe.db.commit()
	return {
		"custom_fields": sum(len(v) for v in CUSTOM_FIELDS.values()) + (len(CRM_FIELDS["CRM Deal"]) if crm else 0),
		"crm_fields": crm,
		"seeded": seeded,
		"workflow": workflow,
		"workspace": workspace,
		"switches": switches,
	}


def _seed_tree(doctype, title_field, rows):
	if frappe.db.count(doctype):
		return 0
	for name, values in rows:
		doc = frappe.new_doc(doctype)
		doc.set(title_field, name)
		doc.is_group = 0
		doc.update(values)
		doc.insert(ignore_permissions=True)
	return len(rows)


def _settings_defaults():
	"""Give FC Settings its defaults once, so the form shows what the code already assumes."""
	doc = frappe.get_single("FC Settings")
	changed = False
	for field, value in settings.DEFAULTS.items():
		if doc.get(field) in (None, ""):
			doc.set(field, value)
			changed = True
	if not doc.default_release_stages:
		for row in settings.release_stages():
			doc.append("default_release_stages", row)
		changed = True
	if changed:
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)


def _workflow():
	"""QS assesses, PM approves (submits), finance releases. Created once; a client may change
	or deactivate it and a migrate will not put it back."""
	if frappe.db.exists("Workflow", WORKFLOW):
		return "exists"
	for state, style in (("Draft", ""), ("Assessed", "Info"), ("Approved", "Success"), ("Released", "Primary"),
		("Cancelled", "Danger")):
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in ("Assess", "Approve", "Send Back", "Release", "Cancel"):
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)
	missing_roles = [
		role for role in ("Projects User", "Projects Manager", "Accounts Manager") if not frappe.db.exists("Role", role)
	]
	if missing_roles:
		return "skipped: roles missing " + ", ".join(missing_roles)

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW,
			"document_type": "FC Subcontract Certificate",
			"workflow_state_field": "approval_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": "Projects User"},
				{"state": "Assessed", "doc_status": "0", "allow_edit": "Projects Manager"},
				{"state": "Approved", "doc_status": "1", "allow_edit": "Accounts Manager"},
				{"state": "Released", "doc_status": "1", "allow_edit": "Accounts Manager"},
				# Without a cancelled state a workflow offers no Cancel at all, and a wrongly
				# approved certificate could never be put right.
				{"state": "Cancelled", "doc_status": "2", "allow_edit": "Projects Manager"},
			],
			"transitions": [
				{"state": "Draft", "action": "Assess", "next_state": "Assessed", "allowed": "Projects User",
					"allow_self_approval": 1},
				{"state": "Draft", "action": "Assess", "next_state": "Assessed", "allowed": "Projects Manager",
					"allow_self_approval": 1},
				{"state": "Assessed", "action": "Approve", "next_state": "Approved", "allowed": "Projects Manager",
					"allow_self_approval": 1},
				{"state": "Assessed", "action": "Send Back", "next_state": "Draft", "allowed": "Projects Manager",
					"allow_self_approval": 1},
				{"state": "Approved", "action": "Release", "next_state": "Released", "allowed": "Accounts Manager",
					"allow_self_approval": 1},
				{"state": "Approved", "action": "Cancel", "next_state": "Cancelled", "allowed": "Projects Manager",
					"allow_self_approval": 1},
				# A released certificate posted to Intacct still refuses to cancel (its
				# before_cancel); one released while posting was off may be cancelled.
				{"state": "Released", "action": "Cancel", "next_state": "Cancelled", "allowed": "Accounts Manager",
					"allow_self_approval": 1},
			],
		}
	).insert(ignore_permissions=True)
	return "created"


def _sync_switches():
	"""Get this app's switches into Active Modules now, not at the next migrate."""
	try:
		from fuse_core import modules

		modules.sync_modules()
	except Exception:
		frappe.log_error(title="Fuse Construction: could not seed the module switches",
			message=frappe.get_traceback())
		return None
	return [module["key"] for module in registry.get_modules()]


# ──────────────────────────────────────────────────────────────────────────────
# The Construction workspace
# ──────────────────────────────────────────────────────────────────────────────

# A construction login's desk: its default workspace. The name lives in registry.py, which
# also says how fuse_theme draws each shortcut (icon and description, keyed by label).
WORKSPACE = registry.WORKSPACE


def _counted(doctype, filters, words, color):
	"""A shortcut counting what is WAITING, not every record: "1 to approve", not "6".

	Frappe draws the count in the shortcut's colour, and grey when it is nothing.
	"""
	return {"type": "DocType", "link_to": doctype, "stats_filter": json.dumps(filters),
		"format": "{} " + words, "color": color}


def _shortcuts():
	"""(module, band, shortcut). The bands are the desk's three rows: the jobs, the money,
	the site. Labels must match registry.DESK_TILES."""
	return [
		("fc_boq_budget", "Jobs", {"label": "Project Shape", "type": "Report", "link_to": "FC Project Shape",
			"color": "Blue"}),
		("fc_boq_budget", "Jobs", {"label": "Dashboard", "type": "Page", "link_to": "fc-project-dashboard",
			"color": "Blue"}),
		("fc_boq_budget", "Jobs", {"label": "BOQs", **_counted(
			"FC BOQ", {"status": ["in", ["Draft", "Submitted"]]}, "not awarded", "Blue")}),
		("fc_tenders", "Jobs", {"label": "Tenders", **_counted(
			"FC Tender", {"status": ["in", ["Published", "Under Evaluation"]]}, "open", "Orange")}),
		("fc_subcontracts", "Money", {"label": "Subcontracts", **_counted(
			"FC Subcontract", {"docstatus": 0}, "to sign", "Orange")}),
		("fc_subcontracts", "Money", {"label": "Certificates", **_counted(
			"FC Subcontract Certificate", {"docstatus": 0}, "to approve", "Orange")}),
		("fc_client_billing", "Money", {"label": "Valuations", **_counted(
			"FC Client Valuation", {"docstatus": 0}, "draft", "Orange")}),
		("fc_subcontracts", "Money", {"label": "Retention", "type": "Report", "link_to": "FC Retention Ledger",
			"color": "Orange"}),
		("fc_site", "Site", {"label": "Site", "type": "Page", "link_to": "fuse-site", "color": "Green"}),
		("fc_site", "Site", {"label": "Crew Time", **_counted(
			"FC Crew Timesheet", {"status": "Pending Approval"}, "to approve", "Red")}),
		("fc_site", "Site", {"label": "Daily Reports", **_counted(
			"FC Daily Site Report", {"docstatus": 0}, "draft", "Grey")}),
		("fc_documents", "Site", {"label": "Documents", **_counted(
			"FC Document Register", {"status": "Under Review"}, "in review", "Grey")}),
	]


def _doc(label, doctype):
	return {"type": "Link", "label": label, "link_type": "DocType", "link_to": doctype}


def _report(label, report):
	return {"type": "Link", "label": label, "link_type": "Report", "link_to": report, "is_query_report": 1}


def _cards():
	return [
		("fc_boq_budget", "Estimating", [
			_doc("Bill of Quantities", "FC BOQ"),
			_doc("BOQ Template", "FC BOQ Template"),
			_doc("BOQ Section", "FC BOQ Group"),
			_doc("Cost Head", "FC Cost Head"),
			_doc("Quotation", "Quotation"),
			_report("BOQ Summary", "FC BOQ Summary"),
		]),
		("fc_boq_budget", "Cost Control", [
			_report("Project Shape", "FC Project Shape"),
			_doc("Project Budget", "FC Project Budget"),
			_doc("Budget Revision", "FC Budget Revision"),
			_report("Cash Flow Forecast", "FC Cash Flow Forecast"),
			_doc("Purchase Order", "Purchase Order"),
		]),
		("fc_tenders", "Tenders", [
			_doc("Tender", "FC Tender"),
			_report("Tender Summary", "FC Tender Summary"),
		]),
		("fc_subcontracts", "Subcontracts", [
			_doc("Subcontract", "FC Subcontract"),
			_doc("Subcontract Certificate", "FC Subcontract Certificate"),
			_doc("Retention Release", "FC Retention Release"),
			_report("Subcontract Status", "FC Subcontract Status"),
			_report("Retention Ledger", "FC Retention Ledger"),
		]),
		("fc_client_billing", "Client Billing", [
			_doc("Client Valuation", "FC Client Valuation"),
			_doc("Retention Release", "FC Retention Release"),
			_report("Retention Ledger", "FC Retention Ledger"),
		]),
		("fc_site", "Site", [
			_doc("Crew Timesheet", "FC Crew Timesheet"),
			_doc("Daily Site Report", "FC Daily Site Report"),
			_doc("Material Request", "Material Request"),
			_doc("Purchase Receipt", "Purchase Receipt"),
			_report("Crew Hours", "FC Crew Hours"),
			_report("Payroll Hours Export", "FC Payroll Hours Export"),
		]),
		("fc_documents", "Documents", [
			_doc("Document Register", "FC Document Register"),
		]),
		(None, "Setup", [
			_doc("Construction Settings", "FC Settings"),
			_doc("Employee", "Employee"),
			_doc("Activity Type", "Activity Type"),
			_doc("Activity Cost", "Activity Cost"),
			_doc("Project", "Project"),
		]),
	]


def _active():
	try:
		from fuse_core import modules

		return modules.active_modules()
	except Exception:
		return {}


def build_workspace():
	"""Create or refresh the workspace from this file, leaving out switched-off modules."""
	active = _active()

	def on(key):
		return key is None or active.get(key, True)

	shortcuts = [(band, s) for key, band, s in _shortcuts() if on(key)]
	cards = [(label, links) for key, label, links in _cards() if on(key)]

	if frappe.db.exists("Workspace", WORKSPACE):
		doc = frappe.get_doc("Workspace", WORKSPACE)
		doc.shortcuts = []
		doc.links = []
		# Unrestricted on purpose, as every Fuse workspace: what a user may DO is decided by
		# document permissions, and a leftover role row throws in the desk's show_page.
		doc.roles = []
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = WORKSPACE

	doc.label = WORKSPACE
	doc.title = "Construction"
	# ERPNext's Projects module, NOT this app's: a workspace is only in a user's allowed list
	# if they have access to its module, and that is the module construction users have.
	# The same lesson fuse_projects and fuse_theme learned on 2026-08-19.
	doc.module = "Projects"
	doc.app = "erpnext"
	doc.icon = "project"
	doc.public = 1
	doc.is_hidden = 0
	doc.sequence_id = 3

	def header(key, text):
		return {"id": key, "type": "header", "data": {"text": f'<span class="h4"><b>{text}</b></span>', "col": 12}}

	# Tiles first, four to a row, each band under its own heading; the full menu below.
	content = []
	band = None
	for index, (shortcut_band, shortcut) in enumerate(shortcuts):
		if shortcut_band != band:
			band = shortcut_band
			content.append(header(f"fc_h{index}", band))
		doc.append("shortcuts", dict(shortcut))
		content.append({"id": f"fc_s{index}", "type": "shortcut", "data": {"shortcut_name": shortcut["label"], "col": 3}})
	if cards:
		content.append(header("fc_h_menu", "Everything else"))
	for index, (label, links) in enumerate(cards):
		doc.append("links", {"type": "Card Break", "label": label})
		for link in links:
			doc.append("links", dict(link))
		content.append({"id": f"fc_c{index}", "type": "card", "data": {"card_name": label, "col": 4}})
	doc.content = json.dumps(content)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.save(ignore_permissions=True)
	return doc.name
