"""The site diary: weather, labour, plant, materials, work done, issues, photos, signed.

Submitting signs it off and locks it — a diary that can be edited after the fact is not
evidence in a delay claim. A section % recorded under Work Done moves that section's
progress, the same as the Progress tile on the phone.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from fuse_construction import progress, settings


class FCDailySiteReport(Document):
	def before_insert(self):
		if not self.reported_by:
			self.reported_by = frappe.db.get_value(
				"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
			)

	def validate(self):
		for row in self.activities:
			if row.task and frappe.db.get_value("Task", row.task, "project") != self.project:
				frappe.throw(f"Work done row {row.idx}: {row.task} is not a section of {self.project}.")
			if row.percent_complete not in (None, "") and not 0 <= flt(row.percent_complete) <= 100:
				frappe.throw(f"Work done row {row.idx}: % complete must be between 0 and 100.")
		if not cint(self.labour_count):
			self.labour_count = self._crew_on_site()

	def _crew_on_site(self):
		"""Workers on the day's crew sheets for this project, when nobody counted."""
		sheets = frappe.get_all(
			"FC Crew Timesheet",
			filters={"project": self.project, "work_date": self.report_date, "docstatus": ["<", 2]},
			pluck="name",
		)
		if not sheets:
			return 0
		return len(
			set(
				frappe.get_all(
					"FC Crew Timesheet Row",
					filters={"parent": ["in", sheets], "parenttype": "FC Crew Timesheet"},
					pluck="employee",
				)
			)
		)

	def before_submit(self):
		if not self.signature:
			frappe.throw("Sign the report before submitting it.")
		if settings.flag("require_daily_report_photo") and not self.photos:
			frappe.throw("This site asks for at least one photo on every daily report.")
		self.signed_by = frappe.session.user
		self.signed_on = now_datetime()

	def on_submit(self):
		for row in self.activities:
			if row.task and row.percent_complete not in (None, ""):
				progress.set_task_progress(row.task, row.percent_complete, "Daily report", (self.doctype, self.name))
