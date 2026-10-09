"""Cash Flow Forecast — money expected in and out, month by month.

OUT: subcontract payment schedules (planned rows at their planned date; certified rows at
the certificate's due date) and open construction purchase orders at their delivery date.
IN: client valuations not yet paid, at their due date; planned billing milestones at their
target date, less the retention and advance the client will hold back; client retention
releases at their due date. Paid items (once Intacct reports them) drop out.

A forecast, not a ledger: it is as good as the dates on the schedules.
"""

import frappe
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, today

from fuse_construction import maths


def execute(filters=None):
	filters = frappe._dict(filters or {})
	start = get_first_day(getdate(filters.from_date or today()))
	months = cint(filters.months) or 6
	end = get_last_day(add_months(start, months - 1))

	buckets = {}
	month = start
	while month <= end:
		buckets[month.strftime("%Y-%m")] = {"month": month.strftime("%b %Y"), "money_in": 0.0, "money_out": 0.0,
			"key": month.strftime("%Y-%m")}
		month = add_months(month, 1)

	overdue = {"in": 0.0, "out": 0.0}

	def add(when, amount, direction):
		if not when or not flt(amount):
			return
		when = getdate(when)
		if when < start:
			overdue[direction] += flt(amount)
			when = start
		key = when.strftime("%Y-%m")
		if key in buckets:
			buckets[key]["money_in" if direction == "in" else "money_out"] += flt(amount)

	for when, amount in _subcontract_out(filters.project):
		add(when, amount, "out")
	for when, amount in _orders_out(filters.project):
		add(when, amount, "out")
	for when, amount in _client_in(filters.project):
		add(when, amount, "in")

	rows, running = [], 0.0
	for bucket in buckets.values():
		bucket["money_in"] = maths.money(bucket["money_in"])
		bucket["money_out"] = maths.money(bucket["money_out"])
		bucket["net"] = maths.money(bucket["money_in"] - bucket["money_out"])
		running = maths.money(running + bucket["net"])
		bucket["cumulative"] = running
		rows.append(bucket)

	columns = [
		{"fieldname": "month", "label": "Month", "fieldtype": "Data", "width": 110},
		{"fieldname": "money_in", "label": "In (Clients)", "fieldtype": "Currency", "width": 140},
		{"fieldname": "money_out", "label": "Out (Subcontracts and Orders)", "fieldtype": "Currency", "width": 200},
		{"fieldname": "net", "label": "Net", "fieldtype": "Currency", "width": 130},
		{"fieldname": "cumulative", "label": "Cumulative", "fieldtype": "Currency", "width": 140},
	]
	chart = {
		"data": {
			"labels": [r["month"] for r in rows],
			"datasets": [
				{"name": "In", "values": [r["money_in"] for r in rows], "chartType": "bar"},
				{"name": "Out", "values": [r["money_out"] for r in rows], "chartType": "bar"},
				{"name": "Cumulative", "values": [r["cumulative"] for r in rows], "chartType": "line"},
			],
		},
		"type": "axis-mixed",
		"colors": ["#007E45", "#B91C1C", "#1E40AF"],
	}
	message = None
	if overdue["in"] or overdue["out"]:
		message = (
			f"Already past due and shown in the first month: in "
			f"{frappe.format_value(overdue['in'], {'fieldtype': 'Currency'})}, out "
			f"{frappe.format_value(overdue['out'], {'fieldtype': 'Currency'})}."
		)
	return columns, rows, message, chart


def _subcontract_out(project):
	row = frappe.qb.DocType("FC Subcontract Payment Schedule")
	sub = frappe.qb.DocType("FC Subcontract")
	cert = frappe.qb.DocType("FC Subcontract Certificate")
	query = (
		frappe.qb.from_(row)
		.join(sub)
		.on(sub.name == row.parent)
		.left_join(cert)
		.on(cert.name == row.certificate)
		.select(row.status, row.planned_date, row.amount, row.certified_amount, cert.due_date)
		.where(
			(row.parenttype == "FC Subcontract")
			& (sub.docstatus == 1)
			& (sub.status.notin(["Closed", "Cancelled"]))
			& (row.status != "Paid")
		)
	)
	if project:
		query = query.where(sub.project == project)
	for r in query.run(as_dict=True):
		if r.status == "Planned":
			yield r.planned_date, r.amount
		else:
			yield r.due_date or r.planned_date, r.certified_amount


def _orders_out(project):
	poi = frappe.qb.DocType("Purchase Order Item")
	po = frappe.qb.DocType("Purchase Order")
	query = (
		frappe.qb.from_(poi)
		.join(po)
		.on(po.name == poi.parent)
		.select(poi.schedule_date, poi.base_net_amount, poi.base_net_rate, poi.received_qty, poi.qty)
		.where(
			(po.docstatus == 1)
			& (po.status.notin(["Closed", "Completed", "Cancelled"]))
			& (po.fc_subcontract.isnull() | (po.fc_subcontract == ""))
			& (poi.fc_task.isnotnull())
			& (poi.fc_task != "")
		)
	)
	if project:
		query = query.where(poi.project == project)
	for r in query.run(as_dict=True):
		open_value = flt(r.base_net_amount) - min(flt(r.received_qty), flt(r.qty)) * flt(r.base_net_rate)
		if open_value > 0:
			yield r.schedule_date, open_value


def _client_in(project):
	filters = {"docstatus": 1, "intacct_status": ["!=", "Paid"]}
	if project:
		filters["project"] = project
	for v in frappe.get_all("FC Client Valuation", filters=filters, fields=["due_date", "net_due"]):
		yield v.due_date, v.net_due

	boq_filters = {"docstatus": 1, "status": "Awarded", "contract_model": "EPC"}
	if project:
		boq_filters["project"] = project
	for boq in frappe.get_all(
		"FC BOQ",
		filters=boq_filters,
		fields=["name", "client_retention_percent", "client_advance_percent", "client_retention_held",
			"client_retention_released", "payment_terms_days"],
	):
		held_back = flt(boq.client_retention_percent) + flt(boq.client_advance_percent)
		for m in frappe.get_all(
			"FC Billing Milestone",
			filters={"parent": boq.name, "parenttype": "FC BOQ", "status": "Planned"},
			fields=["target_date", "amount"],
		):
			yield m.target_date, flt(m.amount) * (1 - held_back / 100)

		# What the client still holds, shared across the stages not yet released in
		# proportion to their shares — after a first release, the rest is all the last one's.
		outstanding = flt(boq.client_retention_held) - flt(boq.client_retention_released)
		stages = frappe.get_all(
			"FC Retention Release Stage",
			filters={"parent": boq.name, "parenttype": "FC BOQ", "parentfield": "client_release_stages",
				"status": ["!=", "Released"]},
			fields=["due_date", "share_percent"],
		)
		shares = sum(flt(s.share_percent) for s in stages)
		for stage in stages:
			if stage.due_date and shares:
				yield stage.due_date, maths.money(outstanding * flt(stage.share_percent) / shares)
