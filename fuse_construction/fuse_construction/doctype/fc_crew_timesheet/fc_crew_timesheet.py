"""A foreman's day: who worked, on which section, for how long.

Draft → Pending Approval → Approved (submitted), or back to Returned with a reason. Only
approval makes it a cost: on submit it becomes one ERPNext Timesheet per worker (see
fuse_construction.labour).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from fuse_construction import costing, labour, maths, settings


class FCCrewTimesheet(Document):
	def before_insert(self):
		if self.status not in ("Draft", "Pending Approval"):
			self.status = "Draft"
		if not self.foreman:
			self.foreman = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")

	def validate(self):
		if not self.rows:
			frappe.throw("Add the crew.")
		default_activity = settings.get("default_activity_type")
		if self.task:
			self._check_task(self.task)
		for row in self.rows:
			row.task = row.task or self.task
			row.activity_type = row.activity_type or default_activity
			if not row.task:
				frappe.throw(f"Row {row.idx}: which section did {row.employee_name or row.employee} work on?")
			if not row.activity_type:
				frappe.throw(
					f"Row {row.idx}: choose the activity, or set a default activity type in FC Settings."
				)
			self._check_task(row.task)
			if flt(row.normal_hours) < 0 or flt(row.overtime_hours) < 0:
				frappe.throw(f"Row {row.idx}: hours cannot be negative.")
			if flt(row.normal_hours) + flt(row.overtime_hours) <= 0:
				frappe.throw(f"Row {row.idx}: enter the hours worked.")

		unrated = labour.price_rows(self)
		if unrated and self._action != "submit":
			frappe.msgprint(
				"No costing rate for " + ", ".join(sorted(set(unrated))) + ". Set an Activity Cost for the worker "
				"or a costing rate on the activity type before this is approved.",
				indicator="orange",
				alert=True,
			)
		self._warn_double_booking()

		workers = {row.employee for row in self.rows}
		self.total_workers = len(workers)
		self.total_normal_hours = maths.qty(sum(flt(r.normal_hours) for r in self.rows))
		self.total_overtime_hours = maths.qty(sum(flt(r.overtime_hours) for r in self.rows))
		self.total_hours = maths.qty(self.total_normal_hours + self.total_overtime_hours)
		self.total_cost = maths.money(sum(flt(r.costing_amount) for r in self.rows))

	def _check_task(self, task):
		project = frappe.db.get_value("Task", task, "project")
		if project != self.project:
			frappe.throw(f"{task} is not a section of {self.project}.")

	def _warn_double_booking(self):
		others = frappe.get_all(
			"FC Crew Timesheet Row",
			filters={
				"employee": ["in", [row.employee for row in self.rows]],
				"parenttype": "FC Crew Timesheet",
				"parent": ["!=", self.name or ""],
			},
			fields=["parent", "employee", "employee_name"],
		)
		clashes = set()
		for row in others:
			parent = frappe.db.get_value("FC Crew Timesheet", row.parent, ["work_date", "docstatus"], as_dict=True)
			if parent and str(parent.work_date) == str(self.work_date) and parent.docstatus < 2:
				clashes.add(f"{row.employee_name or row.employee} ({row.parent})")
		if clashes:
			frappe.msgprint(
				"Also booked on another crew sheet today: " + ", ".join(sorted(clashes)),
				indicator="orange",
				alert=True,
			)

	def before_submit(self):
		if not labour.is_approver():
			frappe.throw("Crew time is approved by a supervisor. FC Settings names the role.")
		unrated = labour.price_rows(self)
		if unrated:
			frappe.throw(
				"Cannot approve: no costing rate for " + ", ".join(sorted(set(unrated))) + ". Set an Activity Cost "
				"for the worker, or a costing rate on the activity type."
			)
		self.status = "Approved"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def on_submit(self):
		labour.create_timesheets(self)
		costing.queue_refresh(self.project)

	def on_cancel(self):
		labour.cancel_timesheets(self)
		self.db_set("status", "Cancelled")
		costing.queue_refresh(self.project)
