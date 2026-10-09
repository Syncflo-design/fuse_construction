"""Project Shape — budget against committed, actual and earned value, as a table and a curve.

One project: a row per BOQ section (budget · committed · actual · % complete · EV · PV ·
variances · CPI · SPI · forecast), the cumulative curve of planned, earned, actual and
committed-plus-actual, and the headline figures as cards. No project: the portfolio, one row
per awarded job.

Every number comes from fuse_construction.costing — the same engine as the budget snapshot
and the dashboard — so the three can never disagree.
"""

import frappe
from frappe.utils import getdate, today

from fuse_construction import costing


def execute(filters=None):
	filters = frappe._dict(filters or {})
	as_at = getdate(filters.as_at or today())
	if not filters.project:
		return _portfolio(as_at)

	position = costing.project_position(filters.project, as_at)
	if not position:
		return _section_columns(), [], "This project has no awarded BOQ, so there is no budget to measure against."

	rows = [dict(row, indent=0) for row in position["rows"]]
	total = dict(position["total"], bold=1)
	rows.append(total)

	curve = costing.curve(filters.project, filters.periodicity or "Weekly", as_at)
	chart = None
	if curve and curve["labels"]:
		chart = {
			"data": {"labels": curve["labels"], "datasets": curve["datasets"]},
			"type": "line",
			"lineOptions": {"regionFill": 0, "hideDots": 1},
			"axisOptions": {"xIsSeries": 1},
			"colors": ["#94A3B8", "#007E45", "#B91C1C", "#D97706"],
		}

	message = None
	if curve and curve["periodicity"] != (filters.periodicity or "Weekly"):
		message = "Shown by month: the job is too long to read week by week."
	return _section_columns(), rows, message, chart, _cards(position["total"])


def _section_columns():
	return [
		{"fieldname": "boq_group", "label": "Section", "fieldtype": "Data", "width": 200},
		{"fieldname": "budget", "label": "Budget", "fieldtype": "Currency", "width": 130},
		{"fieldname": "committed", "label": "Committed", "fieldtype": "Currency", "width": 120},
		{"fieldname": "actual", "label": "Actual", "fieldtype": "Currency", "width": 120},
		{"fieldname": "remaining", "label": "Uncommitted", "fieldtype": "Currency", "width": 120},
		{"fieldname": "percent_complete", "label": "% Complete", "fieldtype": "Percent", "width": 95},
		{"fieldname": "earned_value", "label": "Earned (EV)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "planned_value", "label": "Planned (PV)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "cost_variance", "label": "Cost Variance", "fieldtype": "Currency", "width": 120},
		{"fieldname": "schedule_variance", "label": "Schedule Variance", "fieldtype": "Currency", "width": 130},
		{"fieldname": "cpi", "label": "CPI", "fieldtype": "Float", "precision": 2, "width": 65},
		{"fieldname": "spi", "label": "SPI", "fieldtype": "Float", "precision": 2, "width": 65},
		{"fieldname": "forecast", "label": "Forecast at Completion", "fieldtype": "Currency", "width": 150},
		{"fieldname": "variance_at_completion", "label": "Variance at Completion", "fieldtype": "Currency",
			"width": 150},
		{"fieldname": "revisions", "label": "Budget Revisions", "fieldtype": "Currency", "width": 120},
	]


def _cards(total):
	def ratio(value):
		return round(value, 2) if value is not None else "—"

	indicator = {"Green": "Green", "Amber": "Orange", "Red": "Red"}[total["health"]]
	return [
		{"label": "Contract Value", "value": total["contract_value"], "datatype": "Currency", "indicator": "Blue"},
		{"label": "Budget at Completion", "value": total["budget"], "datatype": "Currency", "indicator": "Blue"},
		{"label": "Committed + Actual", "value": total["committed"] + total["actual"], "datatype": "Currency",
			"indicator": "Red" if total["committed"] + total["actual"] > total["budget"] else "Green"},
		{"label": "Earned Value", "value": total["earned_value"], "datatype": "Currency",
			"indicator": "Green" if total["cost_variance"] >= 0 else "Red"},
		{"label": "CPI", "value": ratio(total["cpi"]), "datatype": "Data", "indicator": indicator},
		{"label": "SPI", "value": ratio(total["spi"]), "datatype": "Data", "indicator": indicator},
		{"label": "Forecast at Completion", "value": total["forecast"], "datatype": "Currency",
			"indicator": "Red" if total["forecast"] > total["budget"] else "Green"},
		{"label": f"Health · {total['schedule_status']}", "value": total["health"], "datatype": "Data",
			"indicator": indicator},
	]


def _portfolio(as_at):
	columns = [
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 140},
		{"fieldname": "title", "label": "Job", "fieldtype": "Data", "width": 200},
		{"fieldname": "health", "label": "Health", "fieldtype": "Data", "width": 80},
		{"fieldname": "contract_value", "label": "Contract Value", "fieldtype": "Currency", "width": 130},
		{"fieldname": "budget", "label": "Budget", "fieldtype": "Currency", "width": 130},
		{"fieldname": "committed", "label": "Committed", "fieldtype": "Currency", "width": 120},
		{"fieldname": "actual", "label": "Actual", "fieldtype": "Currency", "width": 120},
		{"fieldname": "percent_complete", "label": "% Complete", "fieldtype": "Percent", "width": 95},
		{"fieldname": "earned_value", "label": "Earned (EV)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "planned_value", "label": "Planned (PV)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "cpi", "label": "CPI", "fieldtype": "Float", "precision": 2, "width": 65},
		{"fieldname": "spi", "label": "SPI", "fieldtype": "Float", "precision": 2, "width": 65},
		{"fieldname": "forecast", "label": "Forecast at Completion", "fieldtype": "Currency", "width": 150},
		{"fieldname": "variance_at_completion", "label": "Variance at Completion", "fieldtype": "Currency",
			"width": 150},
		{"fieldname": "schedule_status", "label": "Schedule", "fieldtype": "Data", "width": 120},
	]
	rows = costing.portfolio(as_at)
	if not rows:
		return columns, [], "No awarded jobs yet. Award a BOQ to start measuring it."

	chart = {
		"data": {
			"labels": [row["title"] for row in rows],
			"datasets": [
				{"name": "Budget", "values": [row["budget"] for row in rows]},
				{"name": "Forecast at Completion", "values": [row["forecast"] for row in rows]},
				{"name": "Actual", "values": [row["actual"] for row in rows]},
			],
		},
		"type": "bar",
		"colors": ["#94A3B8", "#D97706", "#B91C1C"],
	}
	totals = {
		"budget": sum(r["budget"] for r in rows),
		"actual": sum(r["actual"] for r in rows),
		"forecast": sum(r["forecast"] for r in rows),
		"red": sum(1 for r in rows if r["health"] == "Red"),
	}
	cards = [
		{"label": "Jobs", "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": "Budget", "value": totals["budget"], "datatype": "Currency", "indicator": "Blue"},
		{"label": "Actual", "value": totals["actual"], "datatype": "Currency", "indicator": "Grey"},
		{"label": "Forecast at Completion", "value": totals["forecast"], "datatype": "Currency",
			"indicator": "Red" if totals["forecast"] > totals["budget"] else "Green"},
		{"label": "Jobs in the Red", "value": totals["red"], "datatype": "Int",
			"indicator": "Red" if totals["red"] else "Green"},
	]
	return columns, rows, None, chart, cards
