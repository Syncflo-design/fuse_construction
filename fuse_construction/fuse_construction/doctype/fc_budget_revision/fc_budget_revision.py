"""An approved change to a project's budget — the only way it moves after award.

Submitting is the approval, so only roles that may submit (Projects Manager) can move a
budget. A transfer between sections must net to zero: it moves money, it does not make it.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from fuse_construction import costing, maths


class FCBudgetRevision(Document):
	def validate(self):
		boq, sections = costing.budget_sections(self.project)
		if not boq:
			frappe.throw(f"{self.project} has no awarded BOQ, so it has no budget to revise.")
		self.boq = boq.name
		self.budget = frappe.db.get_value("FC Project Budget", {"project": self.project}, "name")

		current = {s.boq_group: s for s in sections}
		seen = set()
		for line in self.lines:
			if line.boq_group in seen:
				frappe.throw(f"{line.boq_group} appears twice. One line per section.")
			seen.add(line.boq_group)
			section = current.get(line.boq_group)
			before = flt(section.budget) if section else 0.0
			# Revisions already counted in `before` include this one once it is submitted;
			# while it is a draft they do not.
			line.current_budget = maths.money(before)
			line.change = maths.money(line.change)
			line.new_budget = maths.money(before + line.change)
			line.task = section.task if section else None
			if line.new_budget < 0:
				frappe.throw(f"{line.boq_group}: the budget cannot go below zero.")

		self.total_change = maths.money(sum(flt(line.change) for line in self.lines))
		if self.revision_type == "Transfer between Sections" and self.total_change != 0:
			frappe.throw(
				f"A transfer moves budget between sections; these lines change the total by "
				f"{frappe.format_value(self.total_change, {'fieldtype': 'Currency'})}."
			)

	def on_submit(self):
		costing.queue_refresh(self.project)

	def on_cancel(self):
		costing.queue_refresh(self.project)


@frappe.whitelist()
def revision_lines(project):
	"""Every section with its current budget, to start a revision from."""
	frappe.has_permission("FC Budget Revision", "create", throw=True)
	_boq, sections = costing.budget_sections(project)
	return [
		{"boq_group": s.boq_group, "task": s.task, "current_budget": s.budget, "change": 0}
		for s in sections
	]
