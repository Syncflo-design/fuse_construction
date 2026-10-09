"""Budget, committed, actual and earned value — the numbers behind "project shape".

One engine, three readers: the Project Shape report, the project dashboard and the FC Project
Budget snapshot all call this module, so they can never disagree with each other.

Where each number comes from:

  * BUDGET — the awarded BOQ's cost per section, plus approved FC Budget Revisions.
  * COMMITTED — open purchase-order value not yet received, and subcontract value not yet
    certified. A rand moves from committed to actual; it is never in both.
  * ACTUAL — goods received against the project (Purchase Receipt), stock issued to it,
    subcontract certificates (gross, less contra-charges) and approved labour (submitted
    Timesheets, at their costing amount).
  * PROGRESS — each section's task % complete, logged in FC Progress Update every time it
    moves, so earned value can be drawn as a curve and not only as today's dot.

Nothing here posts anything, and nothing here reads Intacct. When Intacct-only project costs
are read back (phase 2), they join ACTUAL here — and only entries Fuse did not post itself,
so a cost is never counted twice.
"""

import frappe
from frappe.utils import getdate, now_datetime, today

from fuse_construction import maths

UNALLOCATED = "Unallocated"

# Above this many weekly points the curve switches to monthly. A chart with 300 x-labels
# is a smear, and the shape of a two-year job reads perfectly well by month.
MAX_WEEKLY_POINTS = 104


# ──────────────────────────────────────────────────────────────────────────────
# Budget
# ──────────────────────────────────────────────────────────────────────────────


def awarded_boq(project):
	return frappe.db.get_value(
		"FC BOQ", {"project": project, "status": "Awarded", "docstatus": 1}, "name"
	)


def budget_sections(project):
	"""The job's sections, each with its original budget, revisions and baseline dates.

	Ordered as the BOQ orders them. A section that exists only because a variation added it
	comes after, with no original budget.
	"""
	boq_name = awarded_boq(project)
	if not boq_name:
		return None, []
	boq = frappe.get_doc("FC BOQ", boq_name)

	sections = {}
	for row in boq.sections:
		sections[row.boq_group] = frappe._dict(
			boq_group=row.boq_group,
			task=row.task,
			original=maths.money(row.cost),
			revisions=0.0,
			contract=maths.money(row.contract_value),
			planned_start=row.planned_start or boq.start_date,
			planned_end=row.planned_end or boq.end_date,
		)

	rev = frappe.qb.DocType("FC Budget Revision")
	line = frappe.qb.DocType("FC Budget Revision Line")
	changes = (
		frappe.qb.from_(line)
		.join(rev)
		.on(rev.name == line.parent)
		.select(line.boq_group, line.change)
		.where((rev.project == project) & (rev.docstatus == 1))
	).run(as_dict=True)

	# Only a revision that adds a section needs the task map; most never do.
	group_task = {group: task for task, group in _task_groups(project).items()} if changes else {}
	for change in changes:
		section = sections.get(change.boq_group)
		if not section:
			section = sections[change.boq_group] = frappe._dict(
				boq_group=change.boq_group,
				task=group_task.get(change.boq_group),
				original=0.0,
				revisions=0.0,
				contract=0.0,
				planned_start=boq.start_date,
				planned_end=boq.end_date,
			)
		section.revisions = maths.money(section.revisions + maths.num(change.change))

	for section in sections.values():
		section.budget = maths.money(section.original + section.revisions)
	return boq, list(sections.values())


def contract_value(project, boq):
	"""The contract value, moved by any approved variation that changed it."""
	changed = frappe.get_all(
		"FC Budget Revision",
		filters={"project": project, "docstatus": 1},
		pluck="contract_value_change",
	)
	return maths.money(maths.num(boq.contract_value) + sum(maths.num(v) for v in changed))


def _task_groups(project):
	"""{task: BOQ section} for every task on the project that belongs to a section."""
	groups = {}
	for task in frappe.get_all(
		"Task", filters={"project": project}, fields=["name", "fc_boq_group"]
	):
		if task.fc_boq_group:
			groups[task.name] = task.fc_boq_group
	boq_name = awarded_boq(project)
	if boq_name:
		for row in frappe.get_all(
			"FC BOQ Section", filters={"parent": boq_name, "parenttype": "FC BOQ"},
			fields=["task", "boq_group"],
		):
			if row.task:
				groups[row.task] = row.boq_group
	return groups


# ──────────────────────────────────────────────────────────────────────────────
# Actual cost, as dated events
# ──────────────────────────────────────────────────────────────────────────────


def actual_events(project, groups=None):
	"""Every actual cost on the project: [{date, group, amount, source, via_order}].

	`via_order` marks costs that are the delivery of an order already counted at its full
	value on the committed curve — goods received against a purchase order, work certified
	against a subcontract. The exposure curve skips those so a rand is drawn once.
	"""
	groups = groups if groups is not None else _task_groups(project)
	events = []

	def group_of(task, fallback=None):
		return fallback or groups.get(task) or UNALLOCATED

	# Goods received. The section comes from the receipt line, else from the order line it
	# was received against — a receiving screen that did not copy it must not lose the cost.
	pri = frappe.qb.DocType("Purchase Receipt Item")
	pr = frappe.qb.DocType("Purchase Receipt")
	poi = frappe.qb.DocType("Purchase Order Item")
	po = frappe.qb.DocType("Purchase Order")
	for row in (
		frappe.qb.from_(pri)
		.join(pr)
		.on(pr.name == pri.parent)
		.left_join(poi)
		.on(poi.name == pri.purchase_order_item)
		.left_join(po)
		.on(po.name == pri.purchase_order)
		.select(
			pr.posting_date, pri.fc_task, poi.fc_task.as_("order_task"), pri.base_net_amount,
			pri.purchase_order, po.fc_subcontract,
		)
		.where((pr.docstatus == 1) & (pri.project == project))
	).run(as_dict=True):
		if row.fc_subcontract:
			continue
		events.append(
			{
				"date": getdate(row.posting_date),
				"group": group_of(row.fc_task or row.order_task),
				"amount": maths.num(row.base_net_amount),
				"source": "Goods received",
				"via_order": bool(row.purchase_order),
			}
		)

	# Stock issued to the project. Only issues — a transfer moves stock between stores and
	# costs the job nothing until it is used.
	sed = frappe.qb.DocType("Stock Entry Detail")
	se = frappe.qb.DocType("Stock Entry")
	for row in (
		frappe.qb.from_(sed)
		.join(se)
		.on(se.name == sed.parent)
		.select(se.posting_date, sed.fc_task, sed.amount)
		.where(
			(se.docstatus == 1)
			& (se.purpose == "Material Issue")
			& ((sed.project == project) | ((sed.project.isnull() | (sed.project == "")) & (se.project == project)))
		)
	).run(as_dict=True):
		events.append(
			{
				"date": getdate(row.posting_date),
				"group": group_of(row.fc_task),
				"amount": maths.num(row.amount),
				"source": "Stock issued",
				"via_order": False,
			}
		)

	# Subcontract certificates, line by line, so each section carries its own work.
	line = frappe.qb.DocType("FC Certificate Line")
	cert = frappe.qb.DocType("FC Subcontract Certificate")
	for row in (
		frappe.qb.from_(line)
		.join(cert)
		.on(cert.name == line.parent)
		.select(cert.posting_date, line.boq_group, line.task, line.this_amount)
		.where(
			(cert.docstatus == 1) & (cert.project == project) & (cert.certificate_type == "Progress")
		)
	).run(as_dict=True):
		events.append(
			{
				"date": getdate(row.posting_date),
				"group": group_of(row.task, row.boq_group),
				"amount": maths.num(row.this_amount),
				"source": "Subcontract certified",
				"via_order": True,
			}
		)

	# Contra-charges reduce what the work cost: the subcontractor bears them.
	contra = frappe.qb.DocType("FC Contra Charge")
	for row in (
		frappe.qb.from_(contra)
		.join(cert)
		.on(cert.name == contra.parent)
		.select(cert.posting_date, contra.boq_group, contra.task, contra.amount)
		.where((cert.docstatus == 1) & (cert.project == project) & (contra.parenttype == "FC Subcontract Certificate"))
	).run(as_dict=True):
		events.append(
			{
				"date": getdate(row.posting_date),
				"group": group_of(row.task, row.boq_group),
				"amount": -maths.num(row.amount),
				"source": "Contra-charge",
				"via_order": True,
			}
		)

	# Approved labour. Submitted Timesheets only: a draft is a claim, not a cost.
	tsd = frappe.qb.DocType("Timesheet Detail")
	ts = frappe.qb.DocType("Timesheet")
	for row in (
		frappe.qb.from_(tsd)
		.join(ts)
		.on(ts.name == tsd.parent)
		.select(tsd.from_time, tsd.task, tsd.costing_amount, tsd.base_costing_amount)
		.where((ts.docstatus == 1) & (tsd.project == project))
	).run(as_dict=True):
		events.append(
			{
				"date": getdate(row.from_time),
				"group": group_of(row.task),
				"amount": maths.num(row.base_costing_amount) or maths.num(row.costing_amount),
				"source": "Labour",
				"via_order": False,
			}
		)

	return events


# ──────────────────────────────────────────────────────────────────────────────
# Commitments
# ──────────────────────────────────────────────────────────────────────────────


def commitments(project, groups=None):
	"""(open commitment by section now, order events for the exposure curve).

	An order event is the full value of an order on the day it was placed — or, for one
	closed early, only what was actually received or certified against it.
	"""
	groups = groups if groups is not None else _task_groups(project)
	open_by_group = {}
	orders = []

	poi = frappe.qb.DocType("Purchase Order Item")
	po = frappe.qb.DocType("Purchase Order")
	for row in (
		frappe.qb.from_(poi)
		.join(po)
		.on(po.name == poi.parent)
		.select(
			po.transaction_date, po.status, po.fc_subcontract, poi.fc_task, poi.base_net_amount,
			poi.base_net_rate, poi.received_qty, poi.qty,
		)
		.where((po.docstatus == 1) & (poi.project == project))
	).run(as_dict=True):
		# A subcontract's order is a mirror of the subcontract, which is counted below.
		if row.fc_subcontract:
			continue
		group = groups.get(row.fc_task) or UNALLOCATED
		received = maths.money(min(maths.num(row.received_qty), maths.num(row.qty)) * maths.num(row.base_net_rate))
		closed = row.status in ("Closed", "Completed")
		still_open = 0.0 if closed else max(maths.money(maths.num(row.base_net_amount) - received), 0.0)
		open_by_group[group] = maths.money(open_by_group.get(group, 0) + still_open)
		orders.append(
			{
				"date": getdate(row.transaction_date),
				"group": group,
				"amount": received if closed else maths.num(row.base_net_amount),
			}
		)

	line = frappe.qb.DocType("FC Subcontract Line")
	sub = frappe.qb.DocType("FC Subcontract")
	for row in (
		frappe.qb.from_(line)
		.join(sub)
		.on(sub.name == line.parent)
		.select(sub.start_date, sub.creation, sub.status, line.boq_group, line.task, line.amount,
			line.certified_amount)
		.where((sub.docstatus == 1) & (sub.project == project))
	).run(as_dict=True):
		group = row.boq_group or groups.get(row.task) or UNALLOCATED
		closed = row.status == "Closed"
		still_open = 0.0 if closed else max(maths.money(maths.num(row.amount) - maths.num(row.certified_amount)), 0.0)
		open_by_group[group] = maths.money(open_by_group.get(group, 0) + still_open)
		orders.append(
			{
				"date": getdate(row.start_date or row.creation),
				"group": group,
				"amount": maths.num(row.certified_amount) if closed else maths.num(row.amount),
			}
		)

	return open_by_group, orders


# ──────────────────────────────────────────────────────────────────────────────
# Progress
# ──────────────────────────────────────────────────────────────────────────────


def progress_history(project):
	"""{task: [(date, percent), ...]} oldest first."""
	history = {}
	for row in frappe.get_all(
		"FC Progress Update",
		filters={"project": project},
		fields=["task", "progress_date", "percent_complete"],
		order_by="progress_date asc, creation asc",
	):
		history.setdefault(row.task, []).append((getdate(row.progress_date), maths.num(row.percent_complete)))
	return history


def _current_progress(project):
	return {
		row.name: (maths.num(row.progress), getdate(row.modified))
		for row in frappe.get_all("Task", filters={"project": project}, fields=["name", "progress", "modified"])
	}


def progress_at(task, when, history, current):
	"""A task's % complete as it stood on a date.

	From the log where there is one. A task that moved before this app was installed has no
	log, so its present % is taken to date from its last change — the honest earliest point
	anyone can say it was true.
	"""
	points = history.get(task)
	if points:
		value = 0.0
		for day, percent in points:
			if day <= when:
				value = percent
			else:
				break
		return value
	percent, since = current.get(task, (0.0, None))
	return percent if since and since <= when else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# The table: one row per section
# ──────────────────────────────────────────────────────────────────────────────


def project_position(project, as_at=None):
	"""Everything the Project Shape table and the budget snapshot need, for one project.

	Returns None when the project has no awarded BOQ — there is no budget to measure against.
	"""
	as_at = getdate(as_at or today())
	boq, sections = budget_sections(project)
	if not boq:
		return None

	groups = _task_groups(project)
	events = actual_events(project, groups)
	open_by_group, _orders = commitments(project, groups)
	history = progress_history(project)
	current = _current_progress(project)
	project_doc = frappe.db.get_value(
		"Project", project, ["expected_start_date", "expected_end_date", "status"], as_dict=True
	) or frappe._dict()

	actual_by_group = {}
	for event in events:
		if event["date"] <= as_at:
			actual_by_group[event["group"]] = actual_by_group.get(event["group"], 0) + event["amount"]

	rows = []
	known = set()
	for section in sections:
		known.add(section.boq_group)
		start = section.planned_start or project_doc.expected_start_date
		end = section.planned_end or project_doc.expected_end_date
		fraction = maths.planned_fraction(start, end, as_at)
		planned = maths.money(section.budget * (fraction if fraction is not None else 0))
		percent = (
			current.get(section.task, (0.0, None))[0]
			if as_at >= getdate(today())
			else progress_at(section.task, as_at, history, current)
		)
		figures = maths.evm(section.budget, percent, actual_by_group.get(section.boq_group, 0), planned)
		rows.append(
			_row(section, percent, open_by_group.get(section.boq_group, 0), figures)
		)

	# Cost that landed on no section — a receipt without one, labour on a task outside the
	# BOQ. Shown rather than hidden, because an unallocated rand is still spent.
	stray = {g for g in set(actual_by_group) | set(open_by_group) if g not in known}
	for group in sorted(stray):
		figures = maths.evm(0, 0, actual_by_group.get(group, 0), 0)
		rows.append(
			_row(
				frappe._dict(boq_group=group, task=None, original=0, revisions=0, budget=0),
				0,
				open_by_group.get(group, 0),
				figures,
			)
		)

	total = _total(rows)
	total["contract_value"] = contract_value(project, boq)
	total["health"] = maths.health(total["cpi"], total["spi"])
	total["schedule_status"] = maths.schedule_status(total["spi"], project_doc.status == "Completed")
	return {"boq": boq, "rows": rows, "total": total, "as_at": as_at}


def _row(section, percent, committed, figures):
	budget = maths.num(section.budget)
	return {
		"boq_group": section.boq_group,
		"task": section.task,
		"original_budget": maths.money(section.original),
		"revisions": maths.money(section.revisions),
		"budget": maths.money(budget),
		"committed": maths.money(committed),
		"actual": figures["actual_cost"],
		"percent_complete": round(maths.num(percent), 2),
		"earned_value": figures["earned_value"],
		"planned_value": figures["planned_value"],
		"cost_variance": figures["cost_variance"],
		"schedule_variance": figures["schedule_variance"],
		"cpi": figures["cpi"],
		"spi": figures["spi"],
		"forecast": figures["eac"],
		"variance_at_completion": figures["vac"],
		"remaining": maths.money(budget - maths.num(committed) - figures["actual_cost"]),
	}


def _total(rows):
	bac = sum(r["budget"] for r in rows)
	earned = sum(r["earned_value"] for r in rows)
	actual = sum(r["actual"] for r in rows)
	planned = sum(r["planned_value"] for r in rows)
	figures = maths.evm_values(bac, earned, actual, planned)
	return {
		"boq_group": "Total",
		"original_budget": maths.money(sum(r["original_budget"] for r in rows)),
		"revisions": maths.money(sum(r["revisions"] for r in rows)),
		"budget": maths.money(bac),
		"committed": maths.money(sum(r["committed"] for r in rows)),
		"actual": figures["actual_cost"],
		"percent_complete": round(earned / bac * 100, 2) if bac else 0.0,
		"earned_value": figures["earned_value"],
		"planned_value": figures["planned_value"],
		"cost_variance": figures["cost_variance"],
		"schedule_variance": figures["schedule_variance"],
		"cpi": figures["cpi"],
		"spi": figures["spi"],
		# A job's forecast is the sum of its sections' — each section is running at its own
		# rate, and averaging them would let a cheap section hide an expensive one.
		"forecast": maths.money(sum(r["forecast"] for r in rows)),
		"variance_at_completion": maths.money(bac - sum(r["forecast"] for r in rows)),
		"remaining": maths.money(sum(r["remaining"] for r in rows)),
	}


# ──────────────────────────────────────────────────────────────────────────────
# The curve
# ──────────────────────────────────────────────────────────────────────────────


def curve(project, periodicity="Weekly", as_at=None):
	"""Cumulative PV, EV, AC and committed-plus-actual, period by period, up to `as_at`.

	Drawn to the reporting date and no further: a line held flat into the future would read
	as a forecast nobody made.
	"""
	as_at = getdate(as_at or today())
	boq, sections = budget_sections(project)
	if not boq:
		return None

	groups = _task_groups(project)
	events = actual_events(project, groups)
	_open, orders = commitments(project, groups)
	history = progress_history(project)
	current = _current_progress(project)

	starts = [getdate(s.planned_start) for s in sections if s.planned_start]
	starts += [e["date"] for e in events] + [o["date"] for o in orders]
	if boq.start_date:
		starts.append(getdate(boq.start_date))
	start = min(starts) if starts else as_at
	if start > as_at:
		return {"labels": [], "datasets": [], "periodicity": periodicity}

	points = maths.period_ends(start, as_at, periodicity)
	if periodicity == "Weekly" and len(points) > MAX_WEEKLY_POINTS:
		periodicity = "Monthly"
		points = maths.period_ends(start, as_at, periodicity)

	planned, earned, actual, exposure = [], [], [], []
	for point in points:
		when = min(point, as_at)
		pv = 0.0
		ev = 0.0
		for section in sections:
			fraction = maths.planned_fraction(section.planned_start, section.planned_end, when) or 0
			pv += section.budget * fraction
			ev += section.budget * progress_at(section.task, when, history, current) / 100
		planned.append(maths.money(pv))
		earned.append(maths.money(ev))
		actual.append(maths.money(sum(e["amount"] for e in events if e["date"] <= when)))
		exposure.append(
			maths.money(
				sum(o["amount"] for o in orders if o["date"] <= when)
				+ sum(e["amount"] for e in events if e["date"] <= when and not e["via_order"])
			)
		)

	return {
		"labels": [frappe.utils.formatdate(p, "dd MMM yy") for p in points],
		"periodicity": periodicity,
		"datasets": [
			{"name": "Planned (PV)", "values": planned},
			{"name": "Earned (EV)", "values": earned},
			{"name": "Actual (AC)", "values": actual},
			{"name": "Committed + Actual", "values": exposure},
		],
	}


# ──────────────────────────────────────────────────────────────────────────────
# The snapshot on FC Project Budget
# ──────────────────────────────────────────────────────────────────────────────


def ensure_budget(boq):
	"""The project's budget record, created at award."""
	name = frappe.db.get_value("FC Project Budget", {"project": boq.project}, "name")
	if not name:
		doc = frappe.new_doc("FC Project Budget")
		doc.project = boq.project
		doc.boq = boq.name
		doc.company = boq.company
		doc.insert(ignore_permissions=True)
		name = doc.name
	refresh_budget(boq.project)
	return name


def refresh_budget(project):
	"""Bring one project's budget snapshot up to date. Returns the snapshot's name."""
	name = frappe.db.get_value("FC Project Budget", {"project": project}, "name")
	if not name:
		return None
	position = project_position(project)
	if not position:
		return name

	doc = frappe.get_doc("FC Project Budget", name)
	total = position["total"]
	doc.boq = position["boq"].name
	doc.company = position["boq"].company
	doc.contract_value = total["contract_value"]
	doc.original_budget = total["original_budget"]
	doc.approved_revisions = total["revisions"]
	doc.current_budget = total["budget"]
	doc.committed = total["committed"]
	doc.actual_cost = total["actual"]
	doc.uncommitted = total["remaining"]
	doc.percent_spent = (
		round((total["committed"] + total["actual"]) / total["budget"] * 100, 2) if total["budget"] else 0
	)
	doc.percent_complete = total["percent_complete"]
	doc.earned_value = total["earned_value"]
	doc.planned_value = total["planned_value"]
	doc.cpi = total["cpi"] or 0
	doc.spi = total["spi"] or 0
	doc.eac = total["forecast"]
	doc.etc_amount = maths.money(total["forecast"] - total["actual"])
	doc.vac = total["variance_at_completion"]
	doc.health = total["health"]
	doc.schedule_status = total["schedule_status"]
	doc.last_refreshed = now_datetime()
	doc.set("items", [])
	for row in position["rows"]:
		doc.append(
			"items",
			{
				"boq_group": row["boq_group"] if row["boq_group"] != UNALLOCATED else None,
				"task": row["task"],
				"original_budget": row["original_budget"],
				"revisions": row["revisions"],
				"current_budget": row["budget"],
				"committed": row["committed"],
				"actual_cost": row["actual"],
				"percent_complete": row["percent_complete"],
				"earned_value": row["earned_value"],
				"planned_value": row["planned_value"],
				"cost_variance": row["cost_variance"],
				"cpi": row["cpi"] or 0,
				"forecast": row["forecast"],
			},
		)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return doc.name


def queue_refresh(project):
	"""Refresh a project's snapshot after this request commits, once however often asked.

	Every receipt, timesheet and certificate asks; a busy morning on site would otherwise
	recompute the same job dozens of times.
	"""
	if not project or not frappe.db.exists("FC Project Budget", {"project": project}):
		return
	frappe.enqueue(
		"fuse_construction.costing.refresh_budget_job",
		project=project,
		queue="short",
		job_id=f"fc-budget-{project}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def refresh_budget_job(project):
	try:
		refresh_budget(project)
	except Exception:
		frappe.log_error(title=f"FC budget refresh failed: {project}", message=frappe.get_traceback())


def refresh_all():
	"""Daily: every open project's snapshot, so planned value moves on even on a quiet day."""
	for project in frappe.get_all(
		"FC Project Budget", pluck="project"
	):
		if frappe.db.get_value("Project", project, "status") in ("Completed", "Cancelled"):
			continue
		refresh_budget_job(project)
		frappe.db.commit()


def portfolio(as_at=None):
	"""One line per awarded project, for the portfolio view."""
	rows = []
	for boq in frappe.get_all(
		"FC BOQ",
		filters={"status": "Awarded", "docstatus": 1},
		fields=["name", "project", "title"],
		order_by="title asc",
	):
		position = project_position(boq.project, as_at)
		if not position:
			continue
		total = dict(position["total"])
		total["project"] = boq.project
		total["title"] = boq.title
		total["boq"] = boq.name
		rows.append(total)
	return rows
