"""The Site phone screen — the server side.

The fuse_floor rule: ERPNext's forms are desk-shaped, and a foreman with one hand free
wants a list, a number and a green button. Every call here saves an ordinary document —
FC Crew Timesheet, Task, FC Daily Site Report, Material Request, Purchase Receipt — so the
phone and the desk run the same validation and the same hooks. Two front doors, one path.

A whitelisted method is a public endpoint whatever the buttons offer, so each one checks
permission itself before doing anything.
"""

import json

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from fuse_construction import labour, progress, settings

LIST_LIMIT = 50


def _rows(value):
	if isinstance(value, str):
		value = json.loads(value or "[]")
	return value or []


def _guard(doctype, ptype="create"):
	if not frappe.has_permission(doctype, ptype):
		frappe.throw(f"You do not have permission to {ptype} {doctype}.", frappe.PermissionError)


# ──────────────────────────────────────────────────────────────────────────────
# Opening the screen
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def context():
	"""Everything the home screen needs in one call."""
	_guard("Project", "read")
	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "employee_name"], as_dict=True
	)
	awarded = set(frappe.get_all("FC BOQ", filters={"status": "Awarded", "docstatus": 1}, pluck="project"))
	projects = frappe.get_list(
		"Project",
		filters={"status": "Open"},
		fields=["name", "project_name", "company"],
		order_by="project_name asc",
		limit_page_length=200,
	)
	# Construction jobs first: they are what this screen is for.
	projects.sort(key=lambda p: (p.name not in awarded, (p.project_name or p.name).lower()))
	approver = labour.is_approver()
	return {
		"user": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"employee": employee,
		"projects": projects,
		"approver": approver,
		"pending": frappe.db.count("FC Crew Timesheet", {"status": "Pending Approval", "docstatus": 0})
		if approver
		else 0,
		"activity_types": frappe.get_all("Activity Type", filters={"disabled": 0}, pluck="name", order_by="name"),
		"default_activity_type": settings.get("default_activity_type"),
		"standard_day_hours": settings.number("standard_day_hours"),
		"auto_overtime": settings.flag("auto_overtime"),
		"require_photo": settings.flag("require_daily_report_photo"),
		# Other apps' screens, linked only where they exist — a dead link on a phone reads as
		# a broken system.
		"receiving_page": "fuse-receiving" if frappe.db.exists("Page", "fuse-receiving") else None,
		"site_work_page": "fuse-projects-floor" if frappe.db.exists("Page", "fuse-projects-floor") else None,
	}


@frappe.whitelist()
def sections(project):
	"""The project's sections (tasks), BOQ sections first."""
	_guard("Task", "read")
	tasks = frappe.get_list(
		"Task",
		filters={"project": project, "status": ["not in", ["Cancelled", "Template"]]},
		fields=["name", "subject", "progress", "status", "fc_boq_group", "exp_start_date", "exp_end_date"],
		order_by="exp_start_date asc, subject asc",
		limit_page_length=200,
	)
	tasks.sort(key=lambda t: (not t.fc_boq_group,))
	return tasks


# ──────────────────────────────────────────────────────────────────────────────
# Crew time
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def crew(project):
	"""Workers who can be booked, and the crew this user booked last on this project."""
	_guard("FC Crew Timesheet", "create")
	company = frappe.db.get_value("Project", project, "company")
	filters = {"status": "Active"}
	if company:
		filters["company"] = company
	# get_all, not get_list: a foreman (Projects User) usually has no read on Employee, and
	# booking a crew is exactly what the create permission checked above allows.
	workers = frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name", "employee_name", "designation", "fc_worker_type", "fc_trade"],
		order_by="employee_name asc",
		limit_page_length=500,
	)

	last = frappe.get_all(
		"FC Crew Timesheet",
		filters={"project": project, "owner": frappe.session.user, "docstatus": ["<", 2]},
		fields=["name", "work_date"],
		order_by="work_date desc, creation desc",
		limit=1,
	)
	previous = []
	if last:
		previous = frappe.get_all(
			"FC Crew Timesheet Row",
			filters={"parent": last[0].name, "parenttype": "FC Crew Timesheet"},
			fields=["employee", "employee_name", "task", "activity_type", "normal_hours", "overtime_hours"],
			order_by="idx asc",
		)
	return {"workers": workers, "previous": previous, "previous_date": last[0].work_date if last else None}


@frappe.whitelist()
def book_crew(project, work_date, rows, task=None, notes=None):
	"""Book a crew's day and send it for approval, in one tap."""
	_guard("FC Crew Timesheet", "create")
	rows = _rows(rows)
	if not rows:
		frappe.throw("Tick at least one worker.")
	doc = frappe.new_doc("FC Crew Timesheet")
	doc.project = project
	doc.work_date = getdate(work_date or nowdate())
	doc.task = task
	doc.notes = notes
	doc.status = "Pending Approval"
	for row in rows:
		doc.append(
			"rows",
			{
				"employee": row.get("employee"),
				"task": row.get("task") or task,
				"activity_type": row.get("activity_type"),
				"normal_hours": flt(row.get("normal_hours")),
				"overtime_hours": flt(row.get("overtime_hours")),
			},
		)
	doc.insert()
	return {
		"name": doc.name,
		"status": doc.status,
		"workers": doc.total_workers,
		"hours": doc.total_hours,
		"overtime": doc.total_overtime_hours,
	}


@frappe.whitelist()
def pending():
	"""Crew sheets waiting for this approver."""
	if not labour.is_approver():
		return []
	sheets = frappe.get_all(
		"FC Crew Timesheet",
		filters={"status": "Pending Approval", "docstatus": 0},
		fields=["name", "work_date", "project", "foreman_name", "owner", "total_workers", "total_hours",
			"total_overtime_hours", "total_cost"],
		order_by="work_date asc, creation asc",
		limit=LIST_LIMIT,
	)
	names = {p.name: p.project_name for p in frappe.get_all(
		"Project", filters={"name": ["in", [s.project for s in sheets] or [""]]}, fields=["name", "project_name"]
	)}
	for sheet in sheets:
		sheet.project_name = names.get(sheet.project, sheet.project)
		sheet.booked_by = frappe.db.get_value("User", sheet.owner, "full_name") or sheet.owner
		sheet.rows = frappe.get_all(
			"FC Crew Timesheet Row",
			filters={"parent": sheet.name, "parenttype": "FC Crew Timesheet"},
			fields=["employee_name", "task", "normal_hours", "overtime_hours", "costing_amount"],
			order_by="idx asc",
		)
		subjects = {t.name: t.subject for t in frappe.get_all(
			"Task", filters={"name": ["in", [r.task for r in sheet.rows] or [""]]}, fields=["name", "subject"]
		)}
		for row in sheet.rows:
			row.section = subjects.get(row.task, row.task)
	return sheets


@frappe.whitelist()
def approve(name):
	return labour.approve(name)


@frappe.whitelist()
def send_back(name, reason):
	return labour.send_back(name, reason)


# ──────────────────────────────────────────────────────────────────────────────
# Progress
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def set_progress(task, percent, status=None):
	"""Move a section on from site. Saved as the Task, so every listener hears it."""
	if not frappe.has_permission("Task", "write", doc=task):
		frappe.throw("You do not have permission to update this task.", frappe.PermissionError)
	if status and status not in ("Open", "Working", "Completed"):
		frappe.throw(f"{status} is not a status this screen sets.")
	percent = flt(percent)
	if status == "Completed":
		percent = 100
	elif percent >= 100:
		status = "Completed"
	elif percent > 0 and not status:
		status = "Working"
	doc = progress.set_task_progress(task, percent, "Site", status=status)
	return {"task": doc.name, "progress": doc.progress, "status": doc.status}


# ──────────────────────────────────────────────────────────────────────────────
# Daily report
# ──────────────────────────────────────────────────────────────────────────────

REPORT_FIELDS = (
	"weather", "temperature_c", "site_condition", "labour_count", "lost_hours", "issues", "safety",
	"instructions", "visitors",
)
REPORT_TABLES = {
	"activities": ("task", "description", "percent_complete", "crew_size"),
	"plant": ("plant", "quantity", "hours", "status", "supplier"),
	"materials": ("item_code", "description", "qty", "uom", "movement", "reference"),
	"photos": ("photo", "caption", "task"),
}


@frappe.whitelist()
def daily_report(project, report_date=None):
	"""Today's draft report on this project by this user — started if there is none."""
	_guard("FC Daily Site Report", "create")
	report_date = getdate(report_date or nowdate())
	name = frappe.db.get_value(
		"FC Daily Site Report",
		{"project": project, "report_date": report_date, "owner": frappe.session.user, "docstatus": 0},
		"name",
	)
	if name:
		doc = frappe.get_doc("FC Daily Site Report", name)
	else:
		doc = frappe.new_doc("FC Daily Site Report")
		doc.project = project
		doc.report_date = report_date
		doc.insert()
	return _report_payload(doc)


def _report_payload(doc):
	payload = {"name": doc.name, "project": doc.project, "report_date": str(doc.report_date)}
	for field in REPORT_FIELDS:
		payload[field] = doc.get(field)
	for table, fields in REPORT_TABLES.items():
		payload[table] = [{f: row.get(f) for f in fields} for row in doc.get(table)]
	return payload


@frappe.whitelist()
def save_daily_report(name, data, sign=None):
	"""Save the report from the phone; with a signature, sign it off and submit it."""
	doc = frappe.get_doc("FC Daily Site Report", name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(f"{doc.name} is already signed off.")
	data = json.loads(data) if isinstance(data, str) else (data or {})
	for field in REPORT_FIELDS:
		if field in data:
			doc.set(field, data[field])
	for table, fields in REPORT_TABLES.items():
		if table in data:
			doc.set(table, [])
			for row in data[table] or []:
				doc.append(table, {f: row.get(f) for f in fields})
	if sign:
		doc.signature = sign
		doc.save()
		doc.submit()
	else:
		doc.save()
	return {"name": doc.name, "docstatus": doc.docstatus}


# ──────────────────────────────────────────────────────────────────────────────
# Material request and receiving
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def items(search=None):
	_guard("Material Request", "create")
	filters = {"disabled": 0, "is_purchase_item": 1, "has_variants": 0}
	or_filters = None
	if search:
		or_filters = {"item_code": ["like", f"%{search}%"], "item_name": ["like", f"%{search}%"]}
	return frappe.get_list(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc",
		limit_page_length=20,
	)


@frappe.whitelist()
def material_request(project, lines, task=None, required_by=None):
	"""Ask the buyer for material, against the project and section. Submitted, so it is live."""
	_guard("Material Request", "create")
	lines = _rows(lines)
	if not lines:
		frappe.throw("Add what is needed.")
	warehouse = settings.get("site_warehouse") or frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if not warehouse:
		frappe.throw("No site warehouse is set in FC Settings, so there is nowhere to deliver to.")
	request = frappe.new_doc("Material Request")
	request.material_request_type = "Purchase"
	request.company = frappe.db.get_value("Project", project, "company")
	request.transaction_date = nowdate()
	request.schedule_date = getdate(required_by) if required_by else add_days(nowdate(), 3)
	request.set_warehouse = warehouse
	for line in lines:
		if flt(line.get("qty")) <= 0:
			continue
		request.append(
			"items",
			{
				"item_code": line.get("item_code"),
				"qty": flt(line.get("qty")),
				"uom": frappe.db.get_value("Item", line.get("item_code"), "stock_uom"),
				"schedule_date": request.schedule_date,
				"warehouse": warehouse,
				"project": project,
				"fc_task": line.get("task") or task,
			},
		)
	if not request.items:
		frappe.throw("Every line needs a quantity.")
	request.insert()
	submitted = False
	if frappe.has_permission("Material Request", "submit", doc=request):
		request.submit()
		submitted = True
	return {"name": request.name, "submitted": submitted}


@frappe.whitelist()
def open_orders(project):
	"""Purchase orders for this project with something still to receive."""
	_guard("Purchase Receipt", "create")
	poi = frappe.qb.DocType("Purchase Order Item")
	po = frappe.qb.DocType("Purchase Order")
	rows = (
		frappe.qb.from_(poi)
		.join(po)
		.on(po.name == poi.parent)
		.select(po.name, po.supplier, po.supplier_name, po.transaction_date)
		.distinct()
		.where(
			(po.docstatus == 1)
			& (poi.project == project)
			& (po.per_received < 100)
			& (po.status.notin(["Closed", "On Hold", "Completed"]))
			& (po.fc_subcontract.isnull() | (po.fc_subcontract == ""))
		)
		.orderby(po.transaction_date)
	).run(as_dict=True)
	return rows


@frappe.whitelist()
def order_lines(purchase_order):
	_guard("Purchase Receipt", "create")
	order = frappe.get_doc("Purchase Order", purchase_order)
	order.check_permission("read")
	return [
		{
			"name": row.name,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"uom": row.uom,
			"ordered": flt(row.qty),
			"received": flt(row.received_qty),
			"outstanding": max(flt(row.qty) - flt(row.received_qty), 0),
		}
		for row in order.items
	]


@frappe.whitelist()
def receive(purchase_order, lines):
	"""Book a delivery in against a purchase order, as a submitted Purchase Receipt.

	Built with ERPNext's own mapping from the order, so the receipt carries everything the
	order did — project and section included — and any app listening to receipts hears it.
	"""
	_guard("Purchase Receipt", "create")
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	wanted = {row.get("name"): flt(row.get("qty")) for row in _rows(lines) if flt(row.get("qty")) > 0}
	if not wanted:
		frappe.throw("Enter what arrived.")
	receipt = make_purchase_receipt(purchase_order)
	receipt.set("items", [row for row in receipt.items if row.purchase_order_item in wanted])
	for row in receipt.items:
		row.qty = wanted[row.purchase_order_item]
		row.received_qty = row.qty
		row.stock_qty = flt(row.qty) * flt(row.conversion_factor or 1)
	receipt.insert()
	receipt.submit()
	return {"name": receipt.name, "lines": cint(len(receipt.items))}
