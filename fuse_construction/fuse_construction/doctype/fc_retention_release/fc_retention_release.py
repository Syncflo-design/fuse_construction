"""Paying back retention, one release stage at a time.

To a subcontractor: what we held on their certificates. From a client: what they held on
our valuations. Either way the amount is the stage's share of everything held to date —
and the last stage pays whatever is left, so nothing is ever stranded by rounding.

Posting (when switched on) moves the amount out of Retention Payable / Retention
Receivable as an AP bill / AR invoice — the same builder as certificates and valuations.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from fuse_construction import maths, retention, settings, subcontracts


class FCRetentionRelease(Document):
	def before_insert(self):
		self.intacct_status = "Not Posted"

	def validate(self):
		if self.release_for == "Subcontractor":
			parent = frappe.get_doc("FC Subcontract", self.subcontract)
			if parent.docstatus != 1:
				frappe.throw(f"Submit {parent.name} first.")
			self.boq = parent.boq
			self.supplier = parent.supplier
			self.customer = None
			stages = parent.release_stages
			held = subcontracts.certificate_history(parent.name).retention_held
			_by_stage, released = subcontracts.released_retention(subcontract=parent.name, exclude=self.name)
		else:
			parent = frappe.get_doc("FC BOQ", self.boq)
			if parent.status != "Awarded" or parent.contract_model != "EPC":
				frappe.throw(f"{parent.name} is not an awarded EPC job, so the client holds no retention.")
			self.subcontract = None
			self.supplier = None
			self.customer = parent.customer
			stages = parent.client_release_stages
			held = maths.money(
				sum(
					frappe.get_all(
						"FC Client Valuation", filters={"boq": parent.name, "docstatus": 1}, pluck="retention_this"
					)
				)
			)
			_by_stage, released = subcontracts.released_retention(boq=parent.name, exclude=self.name)

		self.project = parent.project
		self.company = parent.company

		stage = next((row for row in stages if row.name == self.stage), None) if self.stage else None
		if stage and stage.retention_release and stage.retention_release != self.name:
			frappe.throw(f"Stage {stage.stage_name} was already released by {stage.retention_release}.")
		if not stage:
			stage = retention.next_stage(stages)
		if not stage:
			frappe.throw("Every release stage has already been released.")

		self.stage = stage.name
		self.stage_name = stage.stage_name
		self.share_percent = stage.share_percent
		self.due_date = retention.stage_due_date(stage, parent.practical_completion_date)
		self.retention_held = held
		self.previously_released = released
		self.release_amount = maths.release_amount(
			stage.share_percent, held, released, retention.is_last_open(stages, stage.name)
		)
		if self.release_amount <= 0:
			frappe.throw("There is no retention left to release.")

	def before_submit(self):
		if self.due_date and getdate(self.due_date) > getdate(today()):
			frappe.msgprint(
				f"{self.stage_name} only falls due on {frappe.utils.formatdate(self.due_date)}. "
				"Releasing early — make sure that was agreed.",
				indicator="orange",
				alert=True,
			)
		elif not self.due_date:
			frappe.msgprint(
				f"{self.stage_name} has not been triggered yet (no practical completion or task date).",
				indicator="orange",
				alert=True,
			)

	def on_submit(self):
		if settings.intacct_posting_on():
			from fuse_construction.intacct import posting

			posting.post_release(self)
		self._mark(released=True)

	def before_cancel(self):
		if self.intacct_key:
			frappe.throw(
				f"{self.name} is posted to Intacct as {self.intacct_key}. Reverse it there first."
			)

	def on_cancel(self):
		self._mark(released=False)

	def _mark(self, released):
		if self.release_for == "Subcontractor":
			sub = frappe.get_doc("FC Subcontract", self.subcontract)
			sub.refresh_progress()
			self._tick_schedule(released)
		else:
			boq = frappe.get_doc("FC BOQ", self.boq)
			for row in boq.client_release_stages:
				if row.name == self.stage:
					row.retention_release = self.name if released else None
					row.released_amount = self.release_amount if released else 0
			retention.refresh_stages(boq.client_release_stages, boq.practical_completion_date)
			for row in boq.client_release_stages:
				frappe.db.set_value(
					row.doctype,
					row.name,
					{"retention_release": row.retention_release, "released_amount": row.released_amount,
						"status": row.status, "due_date": row.due_date},
					update_modified=False,
				)
			boq.refresh_client_position()

	def _tick_schedule(self, released):
		filters = {"parent": self.subcontract, "parenttype": "FC Subcontract", "payment_type": "Retention Release"}
		if released:
			rows = frappe.get_all(
				"FC Subcontract Payment Schedule",
				filters={**filters, "status": "Planned"},
				fields=["name", "description"],
				order_by="planned_date asc, idx asc",
			)
			row = next((r for r in rows if r.description == self.stage_name), rows[0] if rows else None)
			if row:
				frappe.db.set_value(
					"FC Subcontract Payment Schedule",
					row.name,
					{"status": "Posted" if self.intacct_key else "Certified", "retention_release": self.name,
						"certified_amount": self.release_amount},
					update_modified=False,
				)
		else:
			for name in frappe.get_all(
				"FC Subcontract Payment Schedule", filters={**filters, "retention_release": self.name}, pluck="name"
			):
				frappe.db.set_value(
					"FC Subcontract Payment Schedule",
					name,
					{"status": "Planned", "retention_release": None, "certified_amount": 0},
					update_modified=False,
				)


@frappe.whitelist()
def open_stages(release_for, name):
	"""The stages still to release, for the stage picker."""
	frappe.has_permission("FC Retention Release", "create", throw=True)
	if release_for == "Subcontractor":
		doc = frappe.get_doc("FC Subcontract", name)
		stages = doc.release_stages
	else:
		doc = frappe.get_doc("FC BOQ", name)
		stages = doc.client_release_stages
	doc.check_permission("read")
	return [
		{"name": row.name, "stage_name": row.stage_name, "share_percent": flt(row.share_percent),
			"due_date": row.due_date, "status": row.status}
		for row in stages
		if not row.retention_release
	]
