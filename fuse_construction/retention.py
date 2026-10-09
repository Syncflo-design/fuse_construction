"""Retention release stages — when each falls due, and telling someone before it does.

The same stage table serves both directions: what we hold from a subcontractor (on FC
Subcontract) and what a client holds from us (on FC BOQ). Practical completion starts the
clock on both; a defects liability period is just "N months after practical completion".
"""

import frappe
from frappe.utils import add_days, add_months, cint, flt, getdate, today


def stage_due_date(stage, pc_date):
	"""When one stage falls due, or None while its trigger has not happened."""
	trigger = stage.trigger
	if trigger == "Practical Completion":
		return getdate(pc_date) if pc_date else None
	if trigger == "Months after Practical Completion":
		return getdate(add_months(pc_date, cint(stage.months_after))) if pc_date else None
	if trigger == "Task Completed":
		if not stage.task:
			return None
		status, completed_on = frappe.db.get_value("Task", stage.task, ["status", "completed_on"]) or (None, None)
		return getdate(completed_on) if status == "Completed" and completed_on else None
	if trigger == "Fixed Date":
		return getdate(stage.fixed_date) if stage.fixed_date else None
	return None


def refresh_stages(stages, pc_date):
	"""Set each stage's due date and status in place. Released stays released."""
	now = getdate(today())
	for row in stages:
		row.due_date = stage_due_date(row, pc_date)
		if row.retention_release:
			row.status = "Released"
		elif row.due_date and getdate(row.due_date) <= now:
			row.status = "Due"
		else:
			row.status = "Pending"


def validate_shares(stages, label):
	"""Shares must add up to 100%, or retention would be left unreleasable — or overpaid."""
	if not stages:
		return
	total = sum(flt(row.share_percent) for row in stages)
	if abs(total - 100) > 0.001:
		frappe.throw(f"{label}: the release stages add up to {total:g}%. They must add up to 100%.")
	for row in stages:
		if row.trigger == "Task Completed" and not row.task:
			frappe.throw(f"{label}: stage {row.stage_name} falls due when a task completes — choose the task.")
		if row.trigger == "Fixed Date" and not row.fixed_date:
			frappe.throw(f"{label}: stage {row.stage_name} falls due on a date — set the date.")


def next_stage(stages):
	"""The first stage not yet released, in table order."""
	for row in stages:
		if not row.retention_release:
			return row
	return None


def is_last_open(stages, stage_name):
	"""Whether every other stage has already been released."""
	return all(row.retention_release for row in stages if row.name != stage_name)


# ──────────────────────────────────────────────────────────────────────────────
# Daily
# ──────────────────────────────────────────────────────────────────────────────


def daily():
	"""Move stages to Due as their dates arrive, and remind the people who release them.

	A reminder goes out twice: when a stage comes within the notice period, and on the day
	it falls due. Twice, not daily — a daily nag for a release waiting on a defects
	inspection teaches people to ignore the bell.
	"""
	notice = cint(frappe.db.get_single_value("FC Settings", "retention_notice_days") or 14)
	role = frappe.db.get_single_value("FC Settings", "retention_notify_role") or "Projects Manager"
	now = getdate(today())
	reminders = []

	for name in frappe.get_all(
		"FC Subcontract", filters={"docstatus": 1, "status": ["not in", ["Closed", "Cancelled"]]}, pluck="name"
	):
		doc = frappe.get_doc("FC Subcontract", name)
		reminders += _refresh_and_collect(doc, "release_stages", doc.practical_completion_date, now, notice,
			f"{doc.title} ({doc.supplier_name or doc.supplier})")

	for name in frappe.get_all("FC BOQ", filters={"docstatus": 1, "status": "Awarded", "contract_model": "EPC"},
		pluck="name"):
		doc = frappe.get_doc("FC BOQ", name)
		reminders += _refresh_and_collect(doc, "client_release_stages", doc.practical_completion_date, now,
			notice, f"{doc.title} (client retention)")

	if reminders:
		_notify(role, reminders)
	frappe.db.commit()
	return len(reminders)


def _refresh_and_collect(doc, table, pc_date, now, notice, label):
	stages = doc.get(table) or []
	before = {row.name: (row.due_date and str(row.due_date), row.status) for row in stages}
	refresh_stages(stages, pc_date)

	reminders = []
	for row in stages:
		# Plain data on a submitted document: write the two cells, not the document, so the
		# daily run never trips a validation that has nothing to do with dates.
		if before[row.name] != (row.due_date and str(row.due_date), row.status):
			frappe.db.set_value(row.doctype, row.name, {"due_date": row.due_date, "status": row.status},
				update_modified=False)
		if row.retention_release or not row.due_date:
			continue
		due = getdate(row.due_date)
		if due == now or due == getdate(add_days(now, notice)):
			reminders.append(
				{
					"doctype": doc.doctype,
					"name": doc.name,
					"subject": f"Retention release {'due today' if due == now else 'due ' + frappe.utils.formatdate(due)}: "
					f"{row.stage_name}, {label}",
				}
			)
	return reminders


def _notify(role, reminders):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	users = [
		user
		for user in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
		if frappe.db.get_value("User", user, "enabled") and user not in ("Administrator", "Guest")
	]
	if not users:
		return
	for reminder in reminders:
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"document_type": reminder["doctype"],
				"document_name": reminder["name"],
				"subject": reminder["subject"],
				"from_user": "Administrator",
			},
		)
