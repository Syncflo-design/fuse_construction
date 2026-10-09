"""Retention Ledger — what is held, what has been released, what is next and when.

Both directions: retention we hold from subcontractors, and retention clients hold from us.
Figures come from submitted certificates, valuations and releases — the same history the
documents themselves use.
"""

import frappe
from frappe.utils import flt, getdate, today

from fuse_construction import maths, retention, subcontracts


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = []
	if filters.direction in (None, "", "Both", "Subcontractors"):
		rows += _subcontractors(filters)
	if filters.direction in (None, "", "Both", "Clients"):
		rows += _clients(filters)
	rows.sort(key=lambda r: (r["next_due"] or getdate("2999-12-31"), r["reference"]))
	cards = [
		{"label": "Held from Subcontractors", "datatype": "Currency", "indicator": "Blue",
			"value": sum(r["outstanding"] for r in rows if r["direction"] == "Subcontractor")},
		{"label": "Held by Clients", "datatype": "Currency", "indicator": "Orange",
			"value": sum(r["outstanding"] for r in rows if r["direction"] == "Client")},
		{"label": "Releases Due Now", "datatype": "Int", "indicator": "Red",
			"value": sum(1 for r in rows if r["next_status"] == "Due")},
	]
	return _columns(), rows, None, None, cards


def _columns():
	return [
		{"fieldname": "direction", "label": "Held From", "fieldtype": "Data", "width": 110},
		{"fieldname": "reference_type", "label": "Type", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "reference", "label": "Contract", "fieldtype": "Dynamic Link", "options": "reference_type",
			"width": 170},
		{"fieldname": "title", "label": "Description", "fieldtype": "Data", "width": 200},
		{"fieldname": "party", "label": "Party", "fieldtype": "Data", "width": 180},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 130},
		{"fieldname": "held", "label": "Held", "fieldtype": "Currency", "width": 120},
		{"fieldname": "released", "label": "Released", "fieldtype": "Currency", "width": 120},
		{"fieldname": "outstanding", "label": "Outstanding", "fieldtype": "Currency", "width": 120},
		{"fieldname": "next_stage", "label": "Next Release", "fieldtype": "Data", "width": 180},
		{"fieldname": "next_amount", "label": "Next Amount (est.)", "fieldtype": "Currency", "width": 130},
		{"fieldname": "next_due", "label": "Due", "fieldtype": "Date", "width": 100},
		{"fieldname": "next_status", "label": "Status", "fieldtype": "Data", "width": 90},
	]


def _next(stages, pc_date, held, released):
	retention.refresh_stages(stages, pc_date)
	stage = retention.next_stage(stages)
	if not stage:
		return None, 0.0, None, "Released"
	amount = maths.release_amount(stage.share_percent, held, released, retention.is_last_open(stages, stage.name))
	return stage.stage_name, amount, stage.due_date, stage.status if stage.due_date else "Waiting on PC"


def _subcontractors(filters):
	conditions = {"docstatus": 1}
	if filters.project:
		conditions["project"] = filters.project
	if filters.supplier:
		conditions["supplier"] = filters.supplier
	rows = []
	for name in frappe.get_all("FC Subcontract", filters=conditions, pluck="name"):
		sub = frappe.get_doc("FC Subcontract", name)
		held = subcontracts.certificate_history(name).retention_held
		_by_stage, released = subcontracts.released_retention(subcontract=name)
		if not held and not filters.show_empty:
			continue
		stage, amount, due, status = _next(sub.release_stages, sub.practical_completion_date, held, released)
		rows.append(_row("Subcontractor", "FC Subcontract", name, sub.title, sub.supplier_name or sub.supplier,
			sub.project, held, released, stage, amount, due, status))
	return rows


def _clients(filters):
	if filters.supplier:
		return []
	conditions = {"docstatus": 1, "status": "Awarded", "contract_model": "EPC"}
	if filters.project:
		conditions["project"] = filters.project
	if filters.customer:
		conditions["customer"] = filters.customer
	rows = []
	for name in frappe.get_all("FC BOQ", filters=conditions, pluck="name"):
		boq = frappe.get_doc("FC BOQ", name)
		held = maths.money(sum(frappe.get_all(
			"FC Client Valuation", filters={"boq": name, "docstatus": 1}, pluck="retention_this")))
		_by_stage, released = subcontracts.released_retention(boq=name)
		if not held and not filters.show_empty:
			continue
		stage, amount, due, status = _next(boq.client_release_stages, boq.practical_completion_date, held, released)
		rows.append(_row("Client", "FC BOQ", name, boq.title, boq.customer, boq.project, held, released,
			stage, amount, due, status))
	return rows


def _row(direction, doctype, name, title, party, project, held, released, stage, amount, due, status):
	return {
		"direction": direction,
		"reference_type": doctype,
		"reference": name,
		"title": title,
		"party": party,
		"project": project,
		"held": held,
		"released": released,
		"outstanding": maths.money(flt(held) - flt(released)),
		"next_stage": stage,
		"next_amount": amount,
		"next_due": getdate(due) if due else None,
		"next_status": status,
		"overdue": bool(due and getdate(due) < getdate(today()) and status != "Released"),
	}
