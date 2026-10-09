"""Billing the client: a measured valuation, a milestone claim, or the advance.

Measured: each section's % complete TO DATE; only the movement since the last valuation is
billed, and submitting moves each section's progress — the same figure the site team sees
and earned value is measured from. Milestone: tick the milestones reached. Advance: the
client's advance, recovered from later valuations in the same proportion.

The client holds retention (up to the contract's cap) and releases it in stages through FC
Retention Release. With posting on, a valuation posts to Intacct as an AR invoice — never an
ERPNext Sales Invoice: Intacct is the ledger.

Adapted from fuse_projects' Fuse Client Valuation (Syncflo).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt

from fuse_construction import costing, maths, progress, settings, subcontracts

VALUATION = "FC Client Valuation"


def history(boq, exclude=None):
	rows = frappe.get_all(
		VALUATION,
		filters={"boq": boq, "docstatus": 1, "name": ["!=", exclude or ""]},
		fields=["name", "valuation_type", "valuation_no", "gross_this_valuation", "retention_this",
			"advance_amount", "advance_recovery_this"],
		order_by="valuation_no desc",
	)
	measured = [r for r in rows if r.valuation_type == "Measured"]
	percents = {}
	if measured:
		for line in frappe.get_all(
			"FC Valuation Line",
			filters={"parent": measured[0].name, "parenttype": VALUATION},
			fields=["boq_group", "percent_complete"],
		):
			percents[line.boq_group] = flt(line.percent_complete)
	return frappe._dict(
		last_no=max((r.valuation_no or 0 for r in rows), default=0),
		valued=maths.money(sum(flt(r.gross_this_valuation) for r in rows if r.valuation_type != "Advance")),
		retention_held=maths.money(sum(flt(r.retention_this) for r in rows)),
		advance_invoiced=maths.money(sum(flt(r.advance_amount) for r in rows)),
		advance_recovered=maths.money(sum(flt(r.advance_recovery_this) for r in rows)),
		last_measured=measured[0].name if measured else None,
		percents=percents,
	)


class FCClientValuation(Document):
	def before_insert(self):
		self.intacct_status = "Not Posted"

	def validate(self):
		boq = frappe.get_doc("FC BOQ", self.boq)
		if boq.status != "Awarded":
			frappe.throw(f"{boq.name} is not awarded.")
		if boq.contract_model != "EPC":
			frappe.throw("An IPP plant is the company's own. It capitalises at COD; there is no client to value it to.")
		basis = {"Measured Valuation": "Measured", "Milestones": "Milestone"}[boq.billing_basis or "Measured Valuation"]
		if self.valuation_type != "Advance" and self.valuation_type != basis:
			frappe.throw(f"{boq.name} bills its client by {boq.billing_basis.lower()}.")

		self.project = boq.project
		self.customer = boq.customer
		self.company = boq.company
		self.contract_value = costing.contract_value(boq.project, boq)
		past = history(boq.name, exclude=self.name)
		if self.is_new() or self._action == "submit" or not self.valuation_no:
			self.valuation_no = past.last_no + 1

		if self.valuation_type == "Advance":
			self._advance(boq, past)
		else:
			if self.valuation_type == "Measured":
				gross_to_date = self._measured(boq, past)
			else:
				gross_to_date = self._milestones(boq, past)
			figures = maths.client_valuation(
				gross_to_date=gross_to_date,
				previously_valued=past.valued,
				contract_value=self.contract_value,
				retention_percent=boq.client_retention_percent,
				retention_cap=maths.pct_of(self.contract_value, boq.client_retention_cap_percent)
				if flt(boq.client_retention_cap_percent)
				else 0,
				retention_held_before=past.retention_held,
				advance_percent=boq.client_advance_percent,
				advance_outstanding=past.advance_invoiced - past.advance_recovered,
			)
			self.gross_to_date = figures["gross_to_date"]
			self.previously_valued = past.valued
			self.gross_this_valuation = figures["gross_this"]
			self.retention_percent = boq.client_retention_percent
			self.retention_this = figures["retention_this"]
			self.advance_recovery_this = figures["advance_recovery_this"]
			self.advance_amount = 0
			self.net_due = figures["net_due"]

		terms = cint(boq.payment_terms_days) or cint(settings.get("payment_terms_days"))
		self.due_date = add_days(self.posting_date, terms)

	def _advance(self, boq, past):
		self.set("lines", [])
		self.set("milestone_lines", [])
		owed = maths.money(maths.pct_of(self.contract_value, boq.client_advance_percent) - past.advance_invoiced)
		if owed <= 0:
			frappe.throw(f"{boq.name} has no client advance left to invoice.")
		for field in ("gross_to_date", "previously_valued", "gross_this_valuation", "retention_this",
			"advance_recovery_this", "retention_percent"):
			self.set(field, 0)
		self.advance_amount = owed
		self.net_due = owed

	def _measured(self, boq, past):
		self.set("milestone_lines", [])
		sections = {row.boq_group: row for row in boq.sections}
		if not self.lines:
			for row in boq.sections:
				self.append("lines", {"boq_group": row.boq_group,
					"percent_complete": past.percents.get(row.boq_group, 0)})
		for line in self.lines:
			section = sections.get(line.boq_group)
			if not section:
				frappe.throw(f"{line.boq_group} is not a section of {boq.name}.")
			percent = flt(line.percent_complete)
			if percent < 0 or percent > 100:
				frappe.throw(f"{line.boq_group}: percent complete must be between 0 and 100.")
			line.task = section.task
			line.contract_value = section.contract_value
			line.previous_percent = past.percents.get(line.boq_group, 0)
			line.value_to_date = maths.pct_of(section.contract_value, percent)
			line.this_value = maths.money(
				line.value_to_date - maths.pct_of(section.contract_value, line.previous_percent)
			)
		return maths.money(sum(flt(line.value_to_date) for line in self.lines))

	def _milestones(self, boq, past):
		self.set("lines", [])
		open_rows = {row.name: row for row in boq.milestones if row.status == "Planned" or row.valuation == self.name}
		if not self.milestone_lines:
			for row in open_rows.values():
				self.append("milestone_lines", {"milestone_row": row.name})
		for line in self.milestone_lines:
			row = open_rows.get(line.milestone_row)
			if not row:
				frappe.throw(f"Milestone row {line.idx} has already been claimed or is not on {boq.name}.")
			line.milestone = row.milestone
			line.boq_group = row.boq_group
			line.percent_of_contract = row.percent_of_contract
			line.amount = row.amount
			line.target_date = row.target_date
		claimed = maths.money(sum(flt(line.amount) for line in self.milestone_lines if line.claim))
		return maths.money(past.valued + claimed)

	def before_submit(self):
		if self.valuation_type != "Advance" and flt(self.gross_this_valuation) <= 0:
			frappe.throw("Nothing new to value since the last valuation.")

	def on_submit(self):
		# Intacct first: a rejected invoice stops the valuation before progress moves.
		if settings.intacct_posting_on():
			from fuse_construction.intacct import posting

			posting.post_valuation(self)
		if self.valuation_type == "Measured":
			for line in self.lines:
				if line.task and flt(line.percent_complete) != flt(line.previous_percent):
					progress.set_task_progress(line.task, line.percent_complete, "Valuation", (self.doctype, self.name))
		elif self.valuation_type == "Milestone":
			self._claim(True)
		frappe.get_doc("FC BOQ", self.boq).refresh_client_position()
		costing.queue_refresh(self.project)

	def before_cancel(self):
		if self.intacct_key:
			frappe.throw(f"{self.name} is posted to Intacct as {self.intacct_key}. Credit it there first.")
		later = frappe.db.get_value(
			VALUATION, {"boq": self.boq, "docstatus": 1, "valuation_no": [">", self.valuation_no]}, "name"
		)
		if later:
			frappe.throw(f"Cancel {later} first. Each valuation builds on the one before it.")
		_by_stage, released = subcontracts.released_retention(boq=self.boq)
		if released > history(self.boq, exclude=self.name).retention_held + 0.005:
			frappe.throw("Retention from this valuation has already been released. Cancel the release first.")

	def on_cancel(self):
		if self.valuation_type == "Measured":
			before = history(self.boq, exclude=self.name).percents
			for line in self.lines:
				if line.task:
					progress.set_task_progress(
						line.task, before.get(line.boq_group, 0), "Valuation cancelled", (self.doctype, self.name)
					)
		elif self.valuation_type == "Milestone":
			self._claim(False)
		frappe.get_doc("FC BOQ", self.boq).refresh_client_position()
		costing.queue_refresh(self.project)

	def _claim(self, claimed):
		for line in self.milestone_lines:
			if line.claim and line.milestone_row:
				frappe.db.set_value(
					"FC Billing Milestone",
					line.milestone_row,
					{"status": "Claimed" if claimed else "Planned", "valuation": self.name if claimed else None},
					update_modified=False,
				)


@frappe.whitelist()
def valuation_rows(boq, valuation_type="Measured"):
	"""The sections (or open milestones) a new valuation starts from."""
	frappe.has_permission(VALUATION, "create", throw=True)
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("read")
	past = history(boq)
	if valuation_type == "Milestone":
		return [
			{"milestone_row": row.name, "milestone": row.milestone, "boq_group": row.boq_group,
				"percent_of_contract": row.percent_of_contract, "amount": row.amount, "target_date": row.target_date}
			for row in doc.milestones
			if row.status == "Planned"
		]
	if valuation_type == "Measured":
		rows = []
		for row in doc.sections:
			previous = past.percents.get(row.boq_group, 0)
			rows.append(
				{"boq_group": row.boq_group, "task": row.task, "contract_value": row.contract_value,
					"previous_percent": previous, "percent_complete": previous,
					"value_to_date": maths.pct_of(row.contract_value, previous), "this_value": 0}
			)
		return rows
	return []
