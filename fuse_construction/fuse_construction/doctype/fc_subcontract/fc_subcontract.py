"""A subcontract: who builds which part of the job, for how much, on what terms.

The terms are the part a spreadsheet gets wrong: an advance paid up front and recovered
from each certificate, retention held on every certificate up to a cap, and released in
stages — typically half at practical completion and half when the defects liability period
ends. The payment schedule says when each payment is expected, and the certificates and
releases tick it off.

Submitting it commits the cost (it shows as committed on the job until certified) and, if
FC Settings says so, raises a matching purchase order so buyers see it too.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, flt, getdate, nowdate

from fuse_construction import costing, maths, retention, settings, subcontracts

TERM_DEFAULTS = {
	"retention_percent": "sub_retention_percent",
	"retention_cap_percent": "sub_retention_cap_percent",
	"advance_percent": "sub_advance_percent",
	"advance_recovery_percent": "sub_advance_recovery_percent",
	"payment_terms_days": "payment_terms_days",
	"dlp_months": "dlp_months",
}


class FCSubcontract(Document):
	def before_insert(self):
		self.company = settings.company(self.company)
		for field, setting in TERM_DEFAULTS.items():
			if self.get(field) is None:
				self.set(field, settings.get(setting))
		if not self.release_stages:
			for row in settings.release_stages():
				if row["trigger"] == "Months after Practical Completion" and self.dlp_months:
					row["months_after"] = cint(self.dlp_months)
				self.append("release_stages", row)
		self.status = "Draft"

	def validate(self):
		self._check_boq()
		self._price_lines()
		self._terms()
		if self.docstatus == 0 and not self.payment_schedule and self.start_date:
			self._build_schedule()
		self._check_schedule()
		if frappe.get_meta("Supplier").has_field("custom_intacct_vendor_id"):
			self.intacct_vendor_id = frappe.db.get_value("Supplier", self.supplier, "custom_intacct_vendor_id")

	def before_submit(self):
		if flt(self.subcontract_value) <= 0:
			frappe.throw("The subcontract has no value.")
		self.status = "Active"

	def on_submit(self):
		if settings.flag("create_subcontract_purchase_order"):
			self._raise_order()
		costing.queue_refresh(self.project)

	def before_update_after_submit(self):
		self._terms()
		if self.practical_completion_date and self.status == "Active":
			self.status = "Practically Complete"
		# A retention release row on the schedule follows its stage's due date once known.
		due = {row.stage_name: row.due_date for row in self.release_stages if row.due_date}
		for row in self.payment_schedule:
			if row.payment_type == "Retention Release" and row.status == "Planned" and due.get(row.description):
				row.planned_date = due[row.description]
		self._check_schedule()

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		# Reopen the tender so the package can be awarded again — and so its link back to
		# this subcontract does not block the cancel.
		if self.tender:
			frappe.db.set_value("FC Tender", self.tender, {"subcontract": None, "status": "Under Evaluation"},
				update_modified=False)
		if self.purchase_order:
			order = frappe.get_doc("Purchase Order", self.purchase_order)
			if order.docstatus == 1:
				order.flags.ignore_permissions = True
				order.cancel()
		costing.queue_refresh(self.project)

	# ── validation ───────────────────────────────────────────────────────────

	def _check_boq(self):
		if not self.boq:
			return
		boq = frappe.db.get_value("FC BOQ", self.boq, ["project", "status"], as_dict=True)
		if boq.status != "Awarded":
			frappe.throw(f"{self.boq} is not awarded yet. A subcontract is let against an open job.")
		if boq.project != self.project:
			frappe.throw(f"{self.boq} runs {boq.project}, not {self.project}.")

	def _price_lines(self):
		tasks = self._section_tasks()
		for row in self.lines:
			if flt(row.qty) <= 0:
				frappe.throw(f"Row {row.idx}: quantity must be more than zero. A lump sum is 1.")
			if flt(row.rate) < 0:
				frappe.throw(f"Row {row.idx}: the rate cannot be negative.")
			row.amount = maths.money(flt(row.qty) * flt(row.rate))
			row.task = tasks.get(row.boq_group) or row.task
		self.subcontract_value = maths.money(sum(flt(row.amount) for row in self.lines))

	def _section_tasks(self):
		"""{section: task} on this project — the BOQ's own, else tasks tagged with a section."""
		tasks = {}
		for task in frappe.get_all(
			"Task", filters={"project": self.project, "fc_boq_group": ["is", "set"]}, fields=["name", "fc_boq_group"]
		):
			tasks.setdefault(task.fc_boq_group, task.name)
		if self.boq:
			for row in frappe.get_all(
				"FC BOQ Section", filters={"parent": self.boq, "parenttype": "FC BOQ"}, fields=["boq_group", "task"]
			):
				if row.task:
					tasks[row.boq_group] = row.task
		return tasks

	def _terms(self):
		if flt(self.advance_percent):
			self.advance_amount = maths.pct_of(self.subcontract_value, self.advance_percent)
		self.advance_amount = maths.money(self.advance_amount)
		if self.advance_amount < 0 or self.advance_amount > flt(self.subcontract_value):
			frappe.throw("The advance must be between nothing and the subcontract value.")
		self.retention_cap_amount = (
			maths.pct_of(self.subcontract_value, self.retention_cap_percent) if flt(self.retention_cap_percent) else 0
		)
		retention.validate_shares(self.release_stages, "Retention release")
		retention.refresh_stages(self.release_stages, self.practical_completion_date)
		self.dlp_end_date = (
			add_months(self.practical_completion_date, cint(self.dlp_months))
			if self.practical_completion_date and cint(self.dlp_months)
			else None
		)

	def _check_schedule(self):
		for row in self.payment_schedule:
			if flt(row.amount) < 0:
				frappe.throw(f"Payment schedule row {row.idx}: the amount cannot be negative.")
		planned = maths.money(sum(flt(row.amount) for row in self.payment_schedule))
		if self.payment_schedule and abs(planned - flt(self.subcontract_value)) > 0.01:
			frappe.msgprint(
				f"The payment schedule adds up to {frappe.format_value(planned, {'fieldtype': 'Currency'})}, "
				f"not the subcontract value of "
				f"{frappe.format_value(self.subcontract_value, {'fieldtype': 'Currency'})}.",
				indicator="orange",
				alert=True,
			)

	# ── payment schedule ─────────────────────────────────────────────────────

	def _build_schedule(self):
		start = getdate(self.start_date)
		end = getdate(self.end_date) if self.end_date else start
		retention_total = (
			min(maths.pct_of(self.subcontract_value, self.retention_percent), self.retention_cap_amount)
			if flt(self.retention_cap_amount)
			else maths.pct_of(self.subcontract_value, self.retention_percent)
		)
		# Until practical completion is known, the end of the work stands in for it.
		stages = []
		for row in self.release_stages:
			date = row.due_date
			if not date:
				if row.trigger == "Months after Practical Completion":
					date = add_months(end, cint(row.months_after))
				elif row.trigger == "Fixed Date":
					date = row.fixed_date
				else:
					date = end
			stages.append((row.stage_name, flt(row.share_percent), getdate(date)))

		rows = maths.payment_plan(
			self.subcontract_value,
			self.advance_amount,
			retention_total,
			maths.month_ends(start, end),
			stages,
		)
		self.set("payment_schedule", [])
		for row in rows:
			row["planned_date"] = row["planned_date"] or start
			self.append("payment_schedule", row)

	@frappe.whitelist()
	def generate_schedule(self):
		"""Rebuild the payment schedule from the value, dates and terms. Draft only."""
		if self.docstatus != 0:
			frappe.throw("The schedule of a submitted subcontract is edited row by row.")
		if not self.start_date:
			frappe.throw("Set the start date first.")
		self._price_lines()
		self._terms()
		self._build_schedule()

	# ── the purchase order ───────────────────────────────────────────────────

	def _raise_order(self):
		"""A submitted purchase order mirroring the subcontract, one line per scope line.

		Raised with the subcontract's authority rather than the user's buying rights: it is a
		mirror of a commitment someone has just approved, not a new purchase. The cost report
		ignores it (it counts the subcontract itself), so the commitment is never double.
		"""
		item_code = settings.get("subcontract_item")
		if not item_code:
			# Nothing is lost without the order: the commitment is counted from the subcontract.
			frappe.msgprint(
				"No purchase order was raised: set the Subcontract Item in FC Settings to have one.",
				indicator="orange",
				alert=True,
			)
			return
		uom = frappe.db.get_value("Item", item_code, "stock_uom")
		schedule_date = max(getdate(self.end_date or add_days(nowdate(), 30)), getdate(nowdate()))

		order = frappe.new_doc("Purchase Order")
		order.supplier = self.supplier
		order.company = self.company
		order.transaction_date = nowdate()
		order.schedule_date = schedule_date
		if order.meta.has_field("project"):
			order.project = self.project
		order.fc_subcontract = self.name
		order.fc_boq = self.boq
		for row in self.lines:
			if flt(row.amount) <= 0:
				continue
			order.append(
				"items",
				{
					"item_code": item_code,
					"description": f"{row.boq_group}: {row.description}",
					"qty": 1,
					"uom": uom,
					"rate": row.amount,
					"schedule_date": schedule_date,
					"project": self.project,
					"fc_task": row.task,
				},
			)
		order.flags.ignore_permissions = True
		order.insert(ignore_permissions=True)
		order.submit()
		self.db_set("purchase_order", order.name)

	# ── progress, from certificates and releases ─────────────────────────────

	def refresh_progress(self):
		"""Totals from submitted certificates and releases, written back to this subcontract."""
		history = subcontracts.certificate_history(self.name)
		by_stage, released = subcontracts.released_retention(subcontract=self.name)

		value = flt(self.subcontract_value)
		values = {
			"certified_to_date": history.certified,
			"contra_to_date": history.contra,
			"net_certified": maths.money(history.certified - history.contra),
			"remaining_to_certify": maths.money(value - history.certified),
			"percent_certified": round(history.certified / value * 100, 2) if value else 0,
			"certificate_count": history.count,
			"advance_paid": history.advance_paid,
			"advance_recovered": history.advance_recovered,
			"advance_outstanding": maths.money(history.advance_paid - history.advance_recovered),
			"retention_held": history.retention_held,
			"retention_released": released,
			"retention_outstanding": maths.money(history.retention_held - released),
		}
		self.db_set(values, update_modified=False)

		for row in self.lines:
			qty_done, amount_done = history.last_lines.get(row.name, (0.0, 0.0))
			frappe.db.set_value(
				row.doctype, row.name, {"certified_qty": qty_done, "certified_amount": amount_done},
				update_modified=False,
			)

		for row in self.release_stages:
			release, amount = by_stage.get(row.name, (None, 0.0))
			row.retention_release = release
			row.released_amount = amount
		retention.refresh_stages(self.release_stages, self.practical_completion_date)
		for row in self.release_stages:
			frappe.db.set_value(
				row.doctype,
				row.name,
				{
					"retention_release": row.retention_release,
					"released_amount": row.released_amount,
					"status": row.status,
					"due_date": row.due_date,
				},
				update_modified=False,
			)
		return values

	@frappe.whitelist()
	def set_practical_completion(self, date):
		"""Record practical completion; the release clock starts from it."""
		self.check_permission("submit")
		if self.docstatus != 1:
			frappe.throw("Submit the subcontract first.")
		self.practical_completion_date = getdate(date)
		self.save()
		return {"due": [(row.stage_name, str(row.due_date or "")) for row in self.release_stages]}

	@frappe.whitelist()
	def close(self):
		"""Final account agreed: nothing more is committed on this subcontract."""
		self.check_permission("submit")
		if flt(self.retention_outstanding) > 0:
			frappe.throw("Retention is still held on this subcontract. Release it before closing.")
		self.status = "Closed"
		self.save()
		costing.queue_refresh(self.project)
		return self.status
