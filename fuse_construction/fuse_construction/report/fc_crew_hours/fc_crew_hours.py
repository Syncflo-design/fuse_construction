"""Crew Hours — booked labour by worker, section, project or day.

Approved crew time by default; tick "Include Pending" to see what is waiting for approval
too. Cost is the crew sheet's own costing, the same figure the Timesheets carry.
"""

import frappe
from frappe.utils import add_days, flt, today

GROUPS = {
	"Worker": ("employee", "employee_name"),
	"Section": ("task", "section"),
	"Project": ("project", "project_name"),
	"Day": ("work_date", None),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = _rows(filters)
	group = filters.group_by or "Worker"
	if group == "Detail":
		return _detail_columns(), rows

	key, label = GROUPS[group]
	totals = {}
	for row in rows:
		bucket = totals.setdefault(
			row[key],
			{"group": row[key], "label": row[label] if label else row[key], "workers": set(), "days": set(),
				"normal_hours": 0.0, "overtime_hours": 0.0, "total_hours": 0.0, "cost": 0.0},
		)
		bucket["workers"].add(row["employee"])
		bucket["days"].add(str(row["work_date"]))
		for field in ("normal_hours", "overtime_hours", "total_hours", "cost"):
			bucket[field] += flt(row[field])
	out = []
	for bucket in totals.values():
		bucket["workers"] = len(bucket["workers"])
		bucket["days"] = len(bucket["days"])
		out.append(bucket)
	out.sort(key=lambda b: str(b["label"] or b["group"]))
	columns = [
		{"fieldname": "label", "label": group, "fieldtype": "Data", "width": 220},
		{"fieldname": "workers", "label": "Workers", "fieldtype": "Int", "width": 80},
		{"fieldname": "days", "label": "Days", "fieldtype": "Int", "width": 70},
		{"fieldname": "normal_hours", "label": "Normal Hours", "fieldtype": "Float", "width": 110},
		{"fieldname": "overtime_hours", "label": "Overtime", "fieldtype": "Float", "width": 100},
		{"fieldname": "total_hours", "label": "Total Hours", "fieldtype": "Float", "width": 110},
		{"fieldname": "cost", "label": "Labour Cost", "fieldtype": "Currency", "width": 130},
	]
	return columns, out


def _rows(filters):
	sheet = frappe.qb.DocType("FC Crew Timesheet")
	row = frappe.qb.DocType("FC Crew Timesheet Row")
	statuses = ["Approved", "Pending Approval"] if filters.include_pending else ["Approved"]
	query = (
		frappe.qb.from_(row)
		.join(sheet)
		.on(sheet.name == row.parent)
		.select(
			sheet.name.as_("crew_timesheet"), sheet.work_date, sheet.project, sheet.status, row.employee,
			row.employee_name, row.task, row.activity_type, row.normal_hours, row.overtime_hours,
			row.total_hours, row.costing_amount.as_("cost"), row.timesheet,
		)
		.where(
			(row.parenttype == "FC Crew Timesheet")
			& (sheet.status.isin(statuses))
			& (sheet.work_date >= (filters.from_date or add_days(today(), -30)))
			& (sheet.work_date <= (filters.to_date or today()))
		)
		.orderby(sheet.work_date)
	)
	if filters.project:
		query = query.where(sheet.project == filters.project)
	if filters.employee:
		query = query.where(row.employee == filters.employee)
	rows = query.run(as_dict=True)

	tasks = {t.name: t.subject for t in frappe.get_all(
		"Task", filters={"name": ["in", list({r.task for r in rows if r.task}) or [""]]}, fields=["name", "subject"]
	)}
	projects = {p.name: p.project_name for p in frappe.get_all(
		"Project", filters={"name": ["in", list({r.project for r in rows}) or [""]]}, fields=["name", "project_name"]
	)}
	for r in rows:
		r.section = tasks.get(r.task, r.task)
		r.project_name = projects.get(r.project, r.project)
	return rows


def _detail_columns():
	return [
		{"fieldname": "work_date", "label": "Date", "fieldtype": "Date", "width": 100},
		{"fieldname": "employee", "label": "Worker", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"fieldname": "employee_name", "label": "Name", "fieldtype": "Data", "width": 160},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 170},
		{"fieldname": "activity_type", "label": "Activity", "fieldtype": "Data", "width": 120},
		{"fieldname": "normal_hours", "label": "Hours", "fieldtype": "Float", "width": 80},
		{"fieldname": "overtime_hours", "label": "OT", "fieldtype": "Float", "width": 70},
		{"fieldname": "cost", "label": "Cost", "fieldtype": "Currency", "width": 110},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
		{"fieldname": "crew_timesheet", "label": "Crew Sheet", "fieldtype": "Link", "options": "FC Crew Timesheet",
			"width": 150},
		{"fieldname": "timesheet", "label": "Timesheet", "fieldtype": "Link", "options": "Timesheet", "width": 130},
	]
