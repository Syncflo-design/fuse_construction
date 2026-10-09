"""Payroll Hours Export — approved hours per worker per day, for the payroll partner.

One row per worker, day and section, normal and overtime apart, Sunday flagged. Export it
from the report menu (CSV or Excel). The exact column layout the payroll partner imports is
still to be agreed; these are the facts any layout is built from, in a stable order.
"""

import frappe
from frappe.utils import getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.from_date or not filters.to_date:
		frappe.throw("Choose the pay period.")

	sheet = frappe.qb.DocType("FC Crew Timesheet")
	row = frappe.qb.DocType("FC Crew Timesheet Row")
	query = (
		frappe.qb.from_(row)
		.join(sheet)
		.on(sheet.name == row.parent)
		.select(
			row.employee, row.employee_name, sheet.work_date, row.normal_hours, row.overtime_hours,
			sheet.project, row.task, row.activity_type, sheet.name.as_("crew_timesheet"), sheet.company,
		)
		.where(
			(row.parenttype == "FC Crew Timesheet")
			& (sheet.docstatus == 1)
			& (sheet.work_date >= filters.from_date)
			& (sheet.work_date <= filters.to_date)
		)
		.orderby(row.employee)
		.orderby(sheet.work_date)
	)
	if filters.company:
		query = query.where(sheet.company == filters.company)
	rows = query.run(as_dict=True)

	employees = {e.name: e for e in frappe.get_all(
		"Employee",
		filters={"name": ["in", list({r.employee for r in rows}) or [""]]},
		fields=["name", "fc_worker_type", "fc_labour_broker"],
	)}
	codes = {b.project: b.project_key for b in frappe.get_all(
		"FC BOQ", filters={"status": "Awarded", "docstatus": 1}, fields=["project", "project_key"]
	)}
	tasks = {t.name: t.subject for t in frappe.get_all(
		"Task", filters={"name": ["in", list({r.task for r in rows if r.task}) or [""]]}, fields=["name", "subject"]
	)}

	out = []
	for r in rows:
		employee = employees.get(r.employee) or frappe._dict()
		if filters.worker_type and employee.fc_worker_type != filters.worker_type:
			continue
		out.append(
			{
				"employee": r.employee,
				"employee_name": r.employee_name,
				"worker_type": employee.fc_worker_type,
				"labour_broker": employee.fc_labour_broker,
				"work_date": r.work_date,
				"sunday": 1 if getdate(r.work_date).weekday() == 6 else 0,
				"normal_hours": r.normal_hours,
				"overtime_hours": r.overtime_hours,
				"project": r.project,
				"project_code": codes.get(r.project),
				"section": tasks.get(r.task, r.task),
				"activity_type": r.activity_type,
				"crew_timesheet": r.crew_timesheet,
			}
		)

	columns = [
		{"fieldname": "employee", "label": "Employee ID", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"fieldname": "employee_name", "label": "Name", "fieldtype": "Data", "width": 170},
		{"fieldname": "worker_type", "label": "Worker Type", "fieldtype": "Data", "width": 120},
		{"fieldname": "labour_broker", "label": "Labour Broker", "fieldtype": "Link", "options": "Supplier",
			"width": 150},
		{"fieldname": "work_date", "label": "Date", "fieldtype": "Date", "width": 100},
		{"fieldname": "sunday", "label": "Sunday", "fieldtype": "Check", "width": 70},
		{"fieldname": "normal_hours", "label": "Normal Hours", "fieldtype": "Float", "width": 110},
		{"fieldname": "overtime_hours", "label": "Overtime Hours", "fieldtype": "Float", "width": 120},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"fieldname": "project_code", "label": "Project Code", "fieldtype": "Data", "width": 110},
		{"fieldname": "section", "label": "Section", "fieldtype": "Data", "width": 170},
		{"fieldname": "activity_type", "label": "Activity", "fieldtype": "Data", "width": 120},
		{"fieldname": "crew_timesheet", "label": "Crew Sheet", "fieldtype": "Link", "options": "FC Crew Timesheet",
			"width": 150},
	]
	return columns, out
