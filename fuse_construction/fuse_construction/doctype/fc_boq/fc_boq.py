"""The bill of quantities: the price, the budget, and the shape of the job.

Draft → Submitted (the price is agreed) → Awarded (the project is open and the cost is its
budget). A revision before award is an amendment, which keeps the history. After award the
BOQ is the baseline and cannot be cancelled: the budget moves only through an approved FC
Budget Revision, so every figure already reported against it stays explainable.

Pricing adapted from fuse_projects' Fuse BOQ (Syncflo) and epcforge's BOQ (MIT, Invento
Software Limited).
"""

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import add_days, cint, flt, getdate

from fuse_construction import commercial, maths, retention, settings

CLIENT_DEFAULTS = (
	"client_retention_percent",
	"client_retention_cap_percent",
	"client_advance_percent",
	"dlp_months",
	"payment_terms_days",
)


class FCBOQ(Document):
	def before_insert(self):
		self.company = settings.company(self.company)
		if self.markup_percent is None:
			self.markup_percent = settings.number("boq_markup_percent")
		for field in CLIENT_DEFAULTS:
			if self.get(field) is None:
				self.set(field, settings.get(field))
		if self.contract_model == "EPC" and not self.client_release_stages:
			for row in settings.release_stages():
				self.append("client_release_stages", row)
		if not (self.project_key or "").strip():
			self.project_key = make_autoname(settings.get("project_code_series"), doc=self)
		self.revision = (
			cint(frappe.db.get_value("FC BOQ", self.amended_from, "revision")) + 1 if self.amended_from else 0
		)
		self.status = "Draft"

	def validate(self):
		self.project_key = (self.project_key or "").strip()
		if self.contract_model == "EPC" and not self.customer:
			frappe.throw("An EPC job is billed to a client. Choose the client.")
		self._check_code()
		self._check_project()
		if self.template and not self.items:
			self._fill_from_template()
		if not self.items:
			frappe.throw("Add at least one line, or choose a template and size the plant.")
		self._price()
		self._sync_sections()
		self._price_milestones()
		if self.contract_model == "EPC":
			retention.validate_shares(self.client_release_stages, "Client retention")
			retention.refresh_stages(self.client_release_stages, self.practical_completion_date)

	def before_submit(self):
		if flt(self.total_cost) <= 0:
			frappe.throw("Price the BOQ before submitting it.")
		self.status = "Submitted"

	def before_update_after_submit(self):
		# Practical completion may be set after submit. The client's release dates follow it.
		if self.contract_model == "EPC":
			retention.validate_shares(self.client_release_stages, "Client retention")
			retention.refresh_stages(self.client_release_stages, self.practical_completion_date)

	def before_cancel(self):
		if self.status == "Awarded":
			frappe.throw(
				"This BOQ is awarded: it is the job's budget, and everything already reported is "
				"measured against it. Change the budget with an FC Budget Revision instead."
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	# ── checks ───────────────────────────────────────────────────────────────

	def _check_code(self):
		clash = frappe.db.get_value(
			"FC BOQ",
			{"project_key": self.project_key, "docstatus": ["<", 2], "name": ["!=", self.name]},
			"name",
		)
		if clash:
			frappe.throw(f"Project code {self.project_key} is already used by {clash}.")

	def _check_project(self):
		if not self.project:
			return
		other = frappe.db.get_value(
			"FC BOQ", {"project": self.project, "docstatus": ["<", 2], "name": ["!=", self.name]}, "name"
		)
		if other:
			frappe.throw(f"{self.project} already has a BOQ: {other}. One BOQ runs one project.")
		company = frappe.db.get_value("Project", self.project, "company")
		if company and company != self.company:
			frappe.throw(f"{self.project} belongs to {company}, not {self.company}.")
		# A project mirrored from Intacct already has its code. The BOQ takes it, so the two
		# can never disagree about what the job is called.
		if frappe.get_meta("Project").has_field("custom_intacct_project_id"):
			intacct_id = frappe.db.get_value("Project", self.project, "custom_intacct_project_id")
			if intacct_id and self.project_key != intacct_id:
				if self.is_new() or not self.project_key:
					self.project_key = intacct_id
				else:
					frappe.throw(
						f"{self.project} is Intacct project {intacct_id}. Set the project code to match."
					)

	# ── pricing ──────────────────────────────────────────────────────────────

	def _fill_from_template(self):
		for line in commercial.template_lines(self.template, self.capacity_kwp, self.storage_kwh):
			self.append("items", line)

	@frappe.whitelist()
	def apply_template(self):
		"""Replace the lines with the template's, sized to the plant on the form."""
		if self.docstatus != 0:
			frappe.throw("Only a draft BOQ can be re-priced from its template.")
		if not self.template:
			frappe.throw("Choose a template first.")
		self.set("items", [])
		self.set("sections", [])
		self.set("milestones", [])
		self._fill_from_template()
		self._price()
		self._sync_sections()
		self._price_milestones()

	def _price(self):
		markup = flt(self.markup_percent)
		by_type = dict.fromkeys(("Material", "Labour", "Plant", "Subcontract", "Overhead"), 0.0)
		for row in self.items:
			if flt(row.qty) < 0 or flt(row.rate) < 0:
				frappe.throw(f"Row {row.idx}: quantity and rate cannot be negative.")
			row.item_type = row.item_type or "Material"
			row.rate = maths.line_rate(row.rate, row.as_dict())
			row.amount = maths.money(flt(row.qty) * flt(row.rate))
			row.sell_amount = maths.sell_value(row.amount, markup)
			row.phase = row.phase or frappe.db.get_value("FC BOQ Group", row.boq_group, "phase")
			by_type[row.item_type] = by_type.get(row.item_type, 0) + row.amount

		self.total_cost = maths.money(sum(flt(row.amount) for row in self.items))
		self.contract_value = maths.sell_value(self.total_cost, markup)
		self.gross_margin = maths.money(self.contract_value - self.total_cost)
		self.gross_margin_percent = (
			round(self.gross_margin / self.contract_value * 100, 2) if self.contract_value else 0
		)
		self.material_cost = maths.money(by_type["Material"])
		self.labour_cost = maths.money(by_type["Labour"])
		self.plant_cost = maths.money(by_type["Plant"])
		self.subcontract_cost = maths.money(by_type["Subcontract"])
		self.overhead_cost = maths.money(by_type["Overhead"])

	def _sync_sections(self):
		"""One section row per section in the lines, in the order they first appear.

		Dates someone has set are kept. A new section takes its window from the template's
		programme, counted from the BOQ's start; failing that, the whole job's window.
		"""
		if self.docstatus != 0:
			return
		plan = commercial.template_plan(self.template)
		existing = {row.boq_group: row for row in self.sections}
		cost, order = {}, []
		for row in self.items:
			if row.boq_group not in cost:
				order.append(row.boq_group)
				cost[row.boq_group] = 0.0
			cost[row.boq_group] += flt(row.amount)

		start = getdate(self.start_date) if self.start_date else None
		rows = []
		for group in order:
			row = existing.get(group)
			values = {
				"boq_group": group,
				"cost": maths.money(cost[group]),
				"contract_value": maths.sell_value(cost[group], self.markup_percent),
				"planned_start": row.planned_start if row else None,
				"planned_end": row.planned_end if row else None,
				"task": row.task if row else None,
			}
			if not values["planned_start"] and start:
				week, duration, _billing = plan.get(group, (None, None, None))
				if week is not None and duration:
					values["planned_start"] = add_days(start, week * 7)
					values["planned_end"] = add_days(values["planned_start"], duration * 7 - 1)
				else:
					values["planned_start"] = start
					values["planned_end"] = self.end_date
			rows.append(values)

		# Section contract values must add up to the contract value exactly, or a job valued
		# at 100% section by section would come out a cent short of done.
		if rows:
			gap = maths.money(flt(self.contract_value) - sum(r["contract_value"] for r in rows))
			if gap:
				largest = max(rows, key=lambda r: r["contract_value"])
				largest["contract_value"] = maths.money(largest["contract_value"] + gap)

		self.set("sections", rows)
		ends = [getdate(r["planned_end"]) for r in rows if r["planned_end"]]
		if not self.end_date and ends:
			self.end_date = max(ends)

	def _price_milestones(self):
		if self.docstatus != 0 or self.contract_model != "EPC" or self.billing_basis != "Milestones":
			return
		if not self.milestones:
			plan = commercial.template_plan(self.template)
			for row in self.sections:
				billing = plan.get(row.boq_group, (None, None, 0))[2]
				if billing:
					self.append(
						"milestones",
						{
							"milestone": f"{row.boq_group} complete",
							"boq_group": row.boq_group,
							"percent_of_contract": billing,
							"target_date": row.planned_end,
						},
					)
		total = sum(flt(row.percent_of_contract) for row in self.milestones)
		if total > 100.001:
			frappe.throw(f"The billing milestones add up to {total:g}% of the contract. They cannot exceed 100%.")
		for row in self.milestones:
			row.amount = maths.pct_of(self.contract_value, row.percent_of_contract)

	# ── client position ──────────────────────────────────────────────────────

	def refresh_client_position(self):
		"""Valued, advance and retention totals with the client, from submitted documents."""
		valuations = frappe.get_all(
			"FC Client Valuation",
			filters={"boq": self.name, "docstatus": 1},
			fields=["valuation_type", "gross_this_valuation", "advance_amount", "advance_recovery_this",
				"retention_this"],
		)
		released = frappe.get_all(
			"FC Retention Release",
			filters={"boq": self.name, "release_for": "Client", "docstatus": 1},
			pluck="release_amount",
		)
		values = {
			"valued_to_date": maths.money(sum(flt(v.gross_this_valuation) for v in valuations
				if v.valuation_type != "Advance")),
			"client_advance_invoiced": maths.money(sum(flt(v.advance_amount) for v in valuations)),
			"client_advance_recovered": maths.money(sum(flt(v.advance_recovery_this) for v in valuations)),
			"client_retention_held": maths.money(sum(flt(v.retention_this) for v in valuations)),
			"client_retention_released": maths.money(sum(flt(r) for r in released)),
		}
		self.db_set(values, update_modified=False)
		return values

	# ── actions ──────────────────────────────────────────────────────────────

	@frappe.whitelist()
	def award(self):
		return commercial.award_boq(self.name)
