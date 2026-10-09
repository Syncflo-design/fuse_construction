"""A project's budget position, kept as a snapshot so lists and dashboards load fast.

Every figure here is written by fuse_construction.costing — never typed. It is refreshed
after anything that moves cost or progress (in the background, once per burst), daily, and
on demand from the form.
"""

import frappe
from frappe.model.document import Document

from fuse_construction import costing


class FCProjectBudget(Document):
	@frappe.whitelist()
	def refresh(self):
		self.check_permission("read")
		costing.refresh_budget(self.project)
		return {"refreshed": True, "project": self.project}
