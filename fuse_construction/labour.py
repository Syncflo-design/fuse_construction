"""Crew time: booked by the foreman, approved by a supervisor, costed to the right section.

The heart of what NSE's own time-card app was trying to do:

  * a foreman books a crew in one go — workers, hours, overtime — against a section (task);
  * a worker's day can be split across sections, one row per section;
  * hours past the standard day become overtime automatically (FC Settings), costed at the
    overtime multiple; Sunday hours at the Sunday multiple;
  * the rate is the worker's own Activity Cost, else their trade's (Activity Type);
  * nothing is a cost until a supervisor approves it. Approval creates one ordinary ERPNext
    Timesheet per worker — which is what lands labour in actual cost, and what fuse_projects
    sends to Intacct when its write-back is on.
"""

import datetime

import frappe
from frappe.utils import add_to_date, flt, get_datetime, getdate, now_datetime

from fuse_construction import maths, settings


def rate_for(employee, activity_type):
	"""Costing rate per hour: the worker's own, else the trade's. None when neither is set.

	The same two places ERPNext's own timesheet looks, in the same order, so the cost shown
	on the crew sheet is the cost the Timesheet will carry.
	"""
	if not activity_type:
		return None
	rate = frappe.db.get_value(
		"Activity Cost", {"employee": employee, "activity_type": activity_type}, "costing_rate"
	)
	if not flt(rate):
		rate = frappe.db.get_value("Activity Type", activity_type, "costing_rate")
	return flt(rate) or None


def is_approver(user=None):
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles & {settings.get("approver_role") or "Projects Manager", "System Manager"})


def price_rows(doc):
	"""Overtime split, rates and cost on every row of a crew timesheet, in place.

	Returns the workers with no rate, so the caller decides whether that is a warning (a
	draft) or a refusal (approval).
	"""
	standard = settings.number("standard_day_hours")
	auto = settings.flag("auto_overtime")
	sunday = getdate(doc.work_date).weekday() == 6

	by_worker = {}
	for row in doc.rows:
		by_worker.setdefault(row.employee, []).append(row)
	for rows in by_worker.values():
		split = maths.split_overtime([(row.normal_hours, row.overtime_hours) for row in rows], standard, auto)
		for row, (normal, overtime) in zip(rows, split, strict=True):
			row.normal_hours, row.overtime_hours = normal, overtime
		if sum(flt(r.normal_hours) + flt(r.overtime_hours) for r in rows) > 24:
			frappe.throw(f"{rows[0].employee_name or rows[0].employee} is booked for more than 24 hours.")

	unrated = []
	for row in doc.rows:
		row.total_hours = maths.qty(flt(row.normal_hours) + flt(row.overtime_hours))
		rate = rate_for(row.employee, row.activity_type)
		if rate is None:
			unrated.append(row.employee_name or row.employee)
			row.costing_rate = 0
			row.costing_amount = 0
			continue
		normal_rate, overtime_rate = maths.labour_rates(
			rate, settings.number("overtime_multiplier"), sunday, settings.number("sunday_multiplier")
		)
		row.costing_rate = rate
		row.costing_amount = maths.money(flt(row.normal_hours) * normal_rate + flt(row.overtime_hours) * overtime_rate)
	return unrated


def _booked_until(employee, work_date):
	"""The end of the latest time already booked for this worker on this day, if any."""
	tsd = frappe.qb.DocType("Timesheet Detail")
	ts = frappe.qb.DocType("Timesheet")
	start = get_datetime(f"{work_date} 00:00:00")
	end = add_to_date(start, days=1)
	rows = (
		frappe.qb.from_(tsd)
		.join(ts)
		.on(ts.name == tsd.parent)
		.select(tsd.to_time)
		.where((ts.employee == employee) & (ts.docstatus < 2) & (tsd.from_time >= start) & (tsd.from_time < end))
	).run(as_dict=True)
	ends = [get_datetime(r.to_time) for r in rows if r.to_time]
	return max(ends) if ends else None


def create_timesheets(doc):
	"""One submitted Timesheet per worker, costed row by row. Called on approval.

	Time windows are laid end to end from the start of the working day — after anything the
	worker already has booked that day — so ERPNext's overlap check never trips on a day
	split across two foremen.
	"""
	day_start = get_datetime(f"{doc.work_date} {settings.get('day_start_time') or '07:00:00'}")
	sunday = getdate(doc.work_date).weekday() == 6
	company = frappe.db.get_value("Project", doc.project, "company")

	by_worker = {}
	for row in doc.rows:
		by_worker.setdefault(row.employee, []).append(row)

	created = []
	for employee, rows in by_worker.items():
		booked = _booked_until(employee, doc.work_date)
		cursor = max(day_start, booked) if booked else day_start

		timesheet = frappe.new_doc("Timesheet")
		timesheet.employee = employee
		timesheet.company = company
		timesheet.fc_crew_timesheet = doc.name
		timesheet.note = f"Crew timesheet {doc.name}, approved by {frappe.session.user}"
		for row in rows:
			normal_rate, overtime_rate = maths.labour_rates(
				row.costing_rate, settings.number("overtime_multiplier"), sunday, settings.number("sunday_multiplier")
			)
			for hours, rate, label in (
				(flt(row.normal_hours), normal_rate, ""),
				(flt(row.overtime_hours), overtime_rate, " — overtime"),
			):
				if hours <= 0:
					continue
				finish = cursor + datetime.timedelta(hours=hours)
				timesheet.append(
					"time_logs",
					{
						"activity_type": row.activity_type,
						"from_time": cursor,
						"to_time": finish,
						"hours": hours,
						"project": doc.project,
						"task": row.task,
						"is_billable": 0,
						"costing_rate": rate,
						"costing_amount": maths.money(rate * hours),
						"description": f"{doc.name}{label}",
					},
				)
				cursor = finish
		timesheet.flags.ignore_permissions = True
		timesheet.insert(ignore_permissions=True)
		timesheet.submit()
		for row in rows:
			row.db_set("timesheet", timesheet.name, update_modified=False)
		created.append(timesheet.name)
	return created


def cancel_timesheets(doc):
	for name in frappe.get_all("Timesheet", filters={"fc_crew_timesheet": doc.name, "docstatus": 1}, pluck="name"):
		timesheet = frappe.get_doc("Timesheet", name)
		if timesheet.get("custom_intacct_key"):
			frappe.throw(
				f"{name} has been sent to Intacct ({timesheet.custom_intacct_key}). Reverse it there before "
				"cancelling the crew time."
			)
		timesheet.flags.ignore_permissions = True
		timesheet.cancel()


# ──────────────────────────────────────────────────────────────────────────────
# The approval flow — the same calls from the phone and the desk
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def submit_for_approval(name):
	doc = frappe.get_doc("FC Crew Timesheet", name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(f"{doc.name} is already {doc.status.lower()}.")
	doc.status = "Pending Approval"
	doc.returned_reason = None
	doc.save()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def approve(name):
	if not is_approver():
		frappe.throw("You cannot approve crew time. FC Settings names the role that can.")
	doc = frappe.get_doc("FC Crew Timesheet", name)
	if doc.docstatus != 0:
		frappe.throw(f"{doc.name} is already {doc.status.lower()}.")
	# The approver's authority comes from FC Settings, which may name a role the doctype's
	# own permissions do not list — a site supervisor, say. Checked above, explicitly.
	doc.flags.ignore_permissions = True
	doc.submit()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def send_back(name, reason):
	if not is_approver():
		frappe.throw("You cannot send crew time back. FC Settings names the role that can.")
	reason = (reason or "").strip()
	if not reason:
		frappe.throw("Say what needs fixing.")
	doc = frappe.get_doc("FC Crew Timesheet", name)
	if doc.docstatus != 0:
		frappe.throw(f"{doc.name} is already {doc.status.lower()}.")
	doc.status = "Returned"
	doc.returned_reason = reason
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", f"Sent back: {frappe.utils.escape_html(reason)}")
	if doc.owner and doc.owner != frappe.session.user:
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": doc.owner,
				"reference_type": doc.doctype,
				"reference_name": doc.name,
				"description": f"Crew time for {doc.work_date} sent back: {reason}",
				"assigned_by": frappe.session.user,
				"date": getdate(now_datetime()),
			}
		).insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}
