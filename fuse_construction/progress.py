"""Section progress: the one number earned value is measured from.

Progress lives on the section's Task, where ERPNext and the site screens already look. Every
change is also written to FC Progress Update with its date and where it came from, because
an earned-value CURVE needs to know what the % was last month, not only what it is today.

All writes go through Task.save, never db.set_value: other apps listen to tasks (fuse_projects
sends progress to Intacct when its write-back is on), and a silent write would skip them.
"""

import frappe
from frappe.utils import flt, today

from fuse_construction import costing


def set_task_progress(task, percent, source, reference=None, status=None):
	"""Move one task's % complete, saying where the figure came from."""
	percent = flt(percent)
	if percent < 0 or percent > 100:
		frappe.throw(f"Percent complete has to be between 0 and 100, not {percent:g}.")
	doc = frappe.get_doc("Task", task)
	if flt(doc.progress) == percent and (not status or doc.status == status):
		return doc
	doc.progress = percent
	if status:
		doc.status = status
	# ERPNext makes these mandatory on a completed task; the screen should not have to ask.
	if doc.status == "Completed":
		if doc.meta.has_field("completed_on") and not doc.get("completed_on"):
			doc.completed_on = today()
		if doc.meta.has_field("completed_by") and not doc.get("completed_by"):
			doc.completed_by = frappe.session.user
	doc.flags.fc_progress_source = source
	doc.flags.fc_progress_reference = reference
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return doc


def on_task_update(doc, method=None):
	"""Log a change in a task's progress. doc_events hook on Task."""
	if not doc.project:
		return
	before = doc.get_doc_before_save()
	previous = flt(before.progress) if before else 0.0
	if flt(doc.progress) == previous and (before or not flt(doc.progress)):
		return

	reference = doc.flags.get("fc_progress_reference") or (None, None)
	frappe.get_doc(
		{
			"doctype": "FC Progress Update",
			"project": doc.project,
			"task": doc.name,
			"progress_date": today(),
			"percent_complete": flt(doc.progress),
			"previous_percent": previous,
			"source": doc.flags.get("fc_progress_source") or "Desk",
			"reference_doctype": reference[0],
			"reference_name": reference[1],
		}
	).insert(ignore_permissions=True)
	costing.queue_refresh(doc.project)
