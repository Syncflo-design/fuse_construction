"""Hooks on ERPNext documents. Each one is small and none of them refuses anything.

This app reads ERPNext's buying, stock and time documents to know what a job has cost; it
does not change how they behave. The only write is filling a section onto a receipt line
that a receiving screen left blank — so the cost lands where the order said it would.
"""

import frappe

from fuse_construction import costing


def purchase_receipt_validate(doc, method=None):
	"""Carry the BOQ section (and project) from the order line onto the receipt line."""
	for row in doc.get("items") or []:
		if not row.get("purchase_order_item") or (row.get("fc_task") and row.get("project")):
			continue
		values = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, ["fc_task", "project"])
		if not values:
			continue
		task, project = values
		if task and not row.get("fc_task"):
			row.fc_task = task
		if project and not row.get("project"):
			row.project = project


def refresh_projects(doc, method=None):
	"""Queue a budget refresh for every project this document touches."""
	projects = set()
	if doc.get("project"):
		projects.add(doc.project)
	for table in ("items", "time_logs"):
		for row in doc.get(table) or []:
			if row.get("project"):
				projects.add(row.project)
	for project in projects:
		costing.queue_refresh(project)


def intacct_settings_updated(doc, method=None):
	"""A module switched on or off: rebuild the workspace so its cards follow.

	Only when a switch actually moved — sync jobs save Intacct Settings all day.
	"""
	from fuse_construction import install

	def switches(settings):
		return {row.module_key: row.enabled for row in (settings.get("active_modules") or [])} if settings else {}

	if switches(doc) == switches(doc.get_doc_before_save()):
		return
	try:
		install.build_workspace()
	except Exception:
		frappe.log_error(title="Fuse Construction: workspace rebuild failed", message=frappe.get_traceback())
