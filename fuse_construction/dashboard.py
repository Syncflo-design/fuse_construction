"""Data for the project dashboard page — one call, everything the page draws.

Layout after epcforge's project dashboard (MIT, Invento Software Limited): contract value,
budget health, procurement coverage, cost by type, milestones, phase progress. The numbers are
fuse_construction.costing's, the same as Project Shape.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate, today

from fuse_construction import costing, maths


@frappe.whitelist()
def projects():
	"""Awarded jobs the user can see, for the picker."""
	frappe.has_permission("FC Project Budget", "read", throw=True)
	return frappe.get_list(
		"FC BOQ",
		filters={"status": "Awarded", "docstatus": 1},
		fields=["project", "title"],
		order_by="title asc",
		limit_page_length=500,
	)


@frappe.whitelist()
def get_data(project, periodicity="Weekly"):
	frappe.has_permission("FC Project Budget", "read", throw=True)
	frappe.has_permission("Project", "read", doc=project, throw=True)
	position = costing.project_position(project)
	if not position:
		return {"project": project, "awarded": False}
	boq = position["boq"]
	total = position["total"]
	project_doc = frappe.db.get_value(
		"Project", project, ["project_name", "status", "customer", "expected_start_date", "expected_end_date"],
		as_dict=True,
	)
	return {
		"awarded": True,
		"project": project,
		"project_name": project_doc.project_name,
		"status": project_doc.status,
		"customer": project_doc.customer,
		"boq": boq.name,
		"title": boq.title,
		"project_key": boq.project_key,
		"contract_model": boq.contract_model,
		"start": project_doc.expected_start_date,
		"end": project_doc.expected_end_date,
		"total": total,
		"sections": position["rows"],
		"curve": costing.curve(project, periodicity),
		"cost_by_type": _cost_by_type(boq, project),
		"phases": _phases(boq),
		"procurement": _procurement(boq, project),
		"subcontracts": _subcontracts(project),
		"client": _client(boq),
		"today": today(),
	}


def _cost_by_type(boq, project):
	budget = {
		"Material": flt(boq.material_cost), "Labour": flt(boq.labour_cost), "Plant": flt(boq.plant_cost),
		"Subcontract": flt(boq.subcontract_cost), "Overhead": flt(boq.overhead_cost),
	}
	actual = dict.fromkeys(budget, 0.0)
	for event in costing.actual_events(project):
		kind = {"Labour": "Labour", "Subcontract certified": "Subcontract", "Contra-charge": "Subcontract"}.get(
			event["source"], "Material"
		)
		actual[kind] += event["amount"]
	return [{"type": k, "budget": maths.money(v), "actual": maths.money(actual[k])} for k, v in budget.items() if v or actual[k]]


def _phases(boq):
	"""Weighted % complete per phase, from each line's section progress."""
	progress = {
		t.name: flt(t.progress)
		for t in frappe.get_all("Task", filters={"project": boq.project}, fields=["name", "progress"])
	}
	phases = {}
	for row in boq.items:
		phase = row.phase or "Unphased"
		bucket = phases.setdefault(phase, {"amount": 0.0, "weighted": 0.0})
		bucket["amount"] += flt(row.amount)
		bucket["weighted"] += flt(row.amount) * progress.get(row.task, 0)
	order = ["Design", "Procurement", "Construction", "Commissioning", "Handover", "Unphased"]
	return [
		{"phase": p, "amount": maths.money(b["amount"]),
			"percent": round(b["weighted"] / b["amount"], 1) if b["amount"] else 0}
		for p, b in sorted(phases.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
	]


def _procurement(boq, project):
	"""Material lines with an item: how much of the BOQ quantity is requested, ordered, received."""
	rows = []
	for line in boq.items:
		if line.item_type != "Material" or not line.item_code or flt(line.qty) <= 0:
			continue
		requested = _sum("Material Request Item", "Material Request", project, line.item_code)
		ordered = _sum("Purchase Order Item", "Purchase Order", project, line.item_code)
		received = _sum("Purchase Receipt Item", "Purchase Receipt", project, line.item_code)
		rows.append(
			{
				"item_code": line.item_code,
				"description": line.description,
				"section": line.boq_group,
				"qty": flt(line.qty),
				"uom": line.uom,
				"requested": min(round(requested / flt(line.qty) * 100, 1), 100),
				"ordered": min(round(ordered / flt(line.qty) * 100, 1), 100),
				"received": min(round(received / flt(line.qty) * 100, 1), 100),
			}
		)
	return rows


def _sum(child, parent, project, item_code):
	c = frappe.qb.DocType(child)
	p = frappe.qb.DocType(parent)
	value = (
		frappe.qb.from_(c)
		.join(p)
		.on(p.name == c.parent)
		.select(Sum(c.stock_qty))
		.where((p.docstatus == 1) & (c.project == project) & (c.item_code == item_code))
	).run()
	return flt(value[0][0]) if value else 0.0


def _subcontracts(project):
	return frappe.get_all(
		"FC Subcontract",
		filters={"project": project, "docstatus": 1},
		fields=["name", "title", "supplier_name", "status", "subcontract_value", "certified_to_date",
			"percent_certified", "retention_outstanding", "advance_outstanding"],
		order_by="title asc",
	)


def _client(boq):
	if boq.contract_model != "EPC":
		return None
	next_milestone = None
	for row in boq.milestones:
		if row.status == "Planned":
			next_milestone = {"milestone": row.milestone, "amount": row.amount, "target_date": row.target_date}
			break
	overdue = [
		r.milestone for r in boq.milestones
		if r.status == "Planned" and r.target_date and getdate(r.target_date) < getdate(today())
	]
	return {
		"contract_value": costing.contract_value(boq.project, boq),
		"valued_to_date": flt(boq.valued_to_date),
		"retention_held": maths.money(flt(boq.client_retention_held) - flt(boq.client_retention_released)),
		"advance_outstanding": maths.money(flt(boq.client_advance_invoiced) - flt(boq.client_advance_recovered)),
		"billing_basis": boq.billing_basis,
		"next_milestone": next_milestone,
		"overdue_milestones": overdue,
	}
