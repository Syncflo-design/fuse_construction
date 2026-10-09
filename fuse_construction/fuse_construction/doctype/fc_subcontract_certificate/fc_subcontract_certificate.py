"""A subcontract certificate: what a subcontractor is paid this period, and why.

Running-account model: each line records the work done TO DATE, and the certificate pays
the movement since the last one. Deductions in order — retention (up to the subcontract's
cap), advance recovery (until the advance is back), contra-charges (each with a reason).
An "Advance Payment" certificate pays the advance itself and nothing else.

Approval, where the site runs the shipped workflow: Draft → Assessed (QS) → Approved (PM,
which submits) → Released (finance). Release is the moment it would post to Intacct as an
AP bill when posting is switched on. Without a workflow, submitting approves and the
Release button releases.

Line model adapted from mradul010/construction_management's RA bill (MIT); the posting it
feeds is fuse_projects.commercial.post_certificate (Syncflo), re-pointed.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt

from fuse_construction import costing, maths, settings, subcontracts


class FCSubcontractCertificate(Document):
	def before_insert(self):
		self.approval_state = "Draft"
		self.intacct_status = "Not Posted"

	def validate(self):
		sub = frappe.get_doc("FC Subcontract", self.subcontract)
		if sub.docstatus != 1:
			frappe.throw(f"Submit {sub.name} before certifying against it.")
		if sub.status in ("Closed", "Cancelled"):
			frappe.throw(f"{sub.name} is {sub.status.lower()}.")
		self.supplier = sub.supplier
		self.project = sub.project
		self.boq = sub.boq
		self.company = sub.company
		self.subcontract_value = sub.subcontract_value

		history = subcontracts.certificate_history(sub.name, exclude=self.name)
		# Numbered at submission, so a draft started first but approved second still takes
		# the later number — the order money is paid in.
		if self.is_new() or self._action == "submit" or not self.certificate_no:
			self.certificate_no = history.last_no + 1

		if self.certificate_type == "Advance Payment":
			self._advance(sub, history)
		else:
			self._progress(sub, history)
		terms = cint(sub.payment_terms_days) or cint(settings.get("payment_terms_days"))
		self.due_date = add_days(self.posting_date, terms)

	def _advance(self, sub, history):
		self.set("lines", [])
		self.set("contra_charges", [])
		owed = maths.money(flt(sub.advance_amount) - history.advance_paid)
		if owed <= 0:
			frappe.throw(
				f"{sub.name} has no advance left to pay."
				if flt(sub.advance_amount)
				else f"{sub.name} carries no advance."
			)
		for field in ("gross_to_date", "previously_certified", "gross_this_certificate", "retention_this",
			"advance_recovery_this", "contra_total", "retention_held_before", "advance_outstanding_before"):
			self.set(field, 0)
		self.advance_payment_amount = owed
		self.net_payable = owed

	def _progress(self, sub, history):
		lines = {row.name: row for row in sub.lines}
		if not self.lines:
			for row in sub.lines:
				previous = history.last_lines.get(row.name, (0.0, 0.0))
				self.append("lines", {"subcontract_line": row.name, "to_date_qty": previous[0]})

		for line in self.lines:
			scope = lines.get(line.subcontract_line)
			if not scope:
				frappe.throw(f"Row {line.idx} is not a line of {sub.name}.")
			previous_qty, previous_amount = history.last_lines.get(scope.name, (0.0, 0.0))
			line.boq_group = scope.boq_group
			line.task = scope.task
			line.description = scope.description
			line.uom = scope.uom
			line.contract_qty = scope.qty
			line.rate = scope.rate
			line.contract_amount = scope.amount
			line.previous_qty = previous_qty
			line.previous_amount = previous_amount
			if line.to_date_qty in (None, "") and flt(line.to_date_percent):
				line.to_date_qty = flt(scope.qty) * flt(line.to_date_percent) / 100
			if flt(line.to_date_qty) < 0:
				frappe.throw(f"Row {line.idx}: work to date cannot be negative.")
			if flt(line.to_date_qty) > flt(scope.qty) + 0.0005:
				frappe.throw(
					f"Row {line.idx} ({scope.description}): {flt(line.to_date_qty):g} to date is more than the "
					f"{flt(scope.qty):g} subcontracted. Vary the subcontract first."
				)
			line.update(
				maths.certificate_line(scope.qty, scope.rate, previous_qty, previous_amount, line.to_date_qty)
			)

		sections = {row.boq_group: row.task for row in sub.lines}
		default_group = sub.lines[0].boq_group if sub.lines else None
		for contra in self.contra_charges:
			if flt(contra.amount) <= 0:
				frappe.throw(f"Contra-charge {contra.idx}: the amount must be more than zero.")
			contra.boq_group = contra.boq_group or default_group
			contra.task = sections.get(contra.boq_group)

		figures = maths.certificate(
			gross_to_date=sum(flt(line.to_date_amount) for line in self.lines),
			previously_certified=history.certified,
			subcontract_value=sub.subcontract_value,
			retention_percent=sub.retention_percent,
			retention_cap=sub.retention_cap_amount,
			retention_held_before=history.retention_held,
			recovery_percent=sub.advance_recovery_percent,
			advance_outstanding=history.advance_paid - history.advance_recovered,
			contra_total=sum(flt(c.amount) for c in self.contra_charges),
		)
		self.retention_percent = sub.retention_percent
		self.retention_cap_amount = sub.retention_cap_amount
		self.retention_held_before = history.retention_held
		self.advance_recovery_percent = sub.advance_recovery_percent
		self.advance_outstanding_before = maths.money(history.advance_paid - history.advance_recovered)
		self.previously_certified = history.certified
		self.gross_to_date = figures["gross_to_date"]
		self.gross_this_certificate = figures["gross_this"]
		self.retention_this = figures["retention_this"]
		self.advance_recovery_this = figures["advance_recovery_this"]
		self.contra_total = figures["contra_total"]
		self.net_payable = figures["net_payable"]
		self.percent_certified = figures["percent_certified"]
		self.advance_payment_amount = 0

		if self.net_payable < 0:
			frappe.throw(
				"The deductions are more than this certificate is worth. Carry part of the "
				"contra-charge to the next certificate."
			)

	def before_submit(self):
		if self.certificate_type == "Progress" and not flt(self.gross_this_certificate) and not flt(self.contra_total):
			frappe.throw("Nothing has moved since the last certificate.")

	def on_submit(self):
		if not subcontracts.workflow_active():
			self.db_set("approval_state", "Approved")
		self._mark_schedule(certified=True)
		self._after_change()

	def on_update_after_submit(self):
		before = self.get_doc_before_save()
		if before and before.approval_state != "Released" and self.approval_state == "Released":
			self._release()

	def before_cancel(self):
		if self.intacct_key:
			frappe.throw(
				f"{self.name} is posted to Intacct as {self.intacct_key}. Reverse the bill in Intacct "
				"first — cancelling it here alone would leave the two systems disagreeing."
			)
		later = frappe.db.get_value(
			"FC Subcontract Certificate",
			{"subcontract": self.subcontract, "docstatus": 1, "certificate_no": [">", self.certificate_no]},
			"name",
		)
		if later:
			frappe.throw(f"Cancel {later} first. Each certificate builds on the one before it.")
		_by_stage, released = subcontracts.released_retention(subcontract=self.subcontract)
		held_after = subcontracts.certificate_history(self.subcontract, exclude=self.name).retention_held
		if released > held_after + 0.005:
			frappe.throw("Retention from this certificate has already been released. Cancel the release first.")

	def on_cancel(self):
		self._mark_schedule(certified=False)
		self._after_change()

	# ── helpers ──────────────────────────────────────────────────────────────

	def _after_change(self):
		frappe.get_doc("FC Subcontract", self.subcontract).refresh_progress()
		costing.queue_refresh(self.project)

	def _mark_schedule(self, certified):
		"""Tick off (or put back) the payment schedule row this certificate pays."""
		if certified:
			wanted = ("Advance",) if self.certificate_type == "Advance Payment" else ("Monthly Progress", "Milestone")
			rows = frappe.get_all(
				"FC Subcontract Payment Schedule",
				filters={"parent": self.subcontract, "parenttype": "FC Subcontract", "status": "Planned",
					"payment_type": ["in", wanted]},
				fields=["name"],
				order_by="planned_date asc, idx asc",
				limit=1,
			)
			if not rows:
				return
			frappe.db.set_value(
				"FC Subcontract Payment Schedule",
				rows[0].name,
				{"status": "Certified", "certificate": self.name, "certified_amount": self.net_payable},
				update_modified=False,
			)
			self.db_set("schedule_row", rows[0].name)
		elif self.schedule_row:
			frappe.db.set_value(
				"FC Subcontract Payment Schedule",
				self.schedule_row,
				{"status": "Planned", "certificate": None, "certified_amount": 0},
				update_modified=False,
			)

	def _release(self):
		"""Released for payment. Intacct first when posting is on; a rejection undoes the release."""
		if settings.intacct_posting_on():
			from fuse_construction.intacct import posting

			posting.post_certificate(self)
			if self.schedule_row:
				frappe.db.set_value("FC Subcontract Payment Schedule", self.schedule_row, "status", "Posted",
					update_modified=False)

	@frappe.whitelist()
	def release(self):
		"""Release for payment, on a site that does not approve certificates by workflow."""
		if subcontracts.workflow_active():
			frappe.throw("Certificates on this site are released through their approval workflow.")
		if not set(frappe.get_roles()) & {"Accounts Manager", "System Manager"}:
			frappe.throw("Only finance (Accounts Manager) releases a certificate for payment.")
		if self.docstatus != 1:
			frappe.throw("Submit the certificate first.")
		if self.approval_state == "Released":
			return self.approval_state
		self.approval_state = "Released"
		self.save(ignore_permissions=True)
		return self.approval_state


@frappe.whitelist()
def certificate_lines(subcontract):
	"""Every line of a subcontract with its previous figures, to start a certificate from."""
	frappe.has_permission("FC Subcontract Certificate", "create", throw=True)
	sub = frappe.get_doc("FC Subcontract", subcontract)
	sub.check_permission("read")
	history = subcontracts.certificate_history(subcontract)
	lines = []
	for row in sub.lines:
		previous_qty, previous_amount = history.last_lines.get(row.name, (0.0, 0.0))
		lines.append(
			{
				"subcontract_line": row.name,
				"boq_group": row.boq_group,
				"task": row.task,
				"description": row.description,
				"uom": row.uom,
				"contract_qty": row.qty,
				"rate": row.rate,
				"contract_amount": row.amount,
				"previous_qty": previous_qty,
				"previous_amount": previous_amount,
				"to_date_qty": previous_qty,
				"to_date_percent": round(previous_qty / flt(row.qty) * 100, 4) if flt(row.qty) else 0,
				"to_date_amount": previous_amount,
				"this_amount": 0,
			}
		)
	return {
		"lines": lines,
		"has_advance_due": maths.money(flt(sub.advance_amount) - history.advance_paid) > 0,
	}
