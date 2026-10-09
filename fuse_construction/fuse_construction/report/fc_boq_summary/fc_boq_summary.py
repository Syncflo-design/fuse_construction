"""BOQ Summary — every BOQ with its cost, contract value, margin and cost mix.

Adapted from epcforge's BOQ Summary (MIT, Invento Software Limited).
"""

import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"docstatus": ["<", 2]}
	for field in ("project", "status", "contract_model", "customer"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	rows = frappe.get_all(
		"FC BOQ",
		filters=conditions,
		fields=["name", "title", "project_key", "project", "customer", "contract_model", "status", "revision",
			"capacity_kwp", "storage_kwh", "total_cost", "contract_value", "gross_margin", "gross_margin_percent",
			"material_cost", "labour_cost", "plant_cost", "subcontract_cost", "overhead_cost"],
		order_by="creation desc",
	)
	for row in rows:
		row.line_count = frappe.db.count("FC BOQ Item", {"parent": row.name, "parenttype": "FC BOQ"})
		size = row.capacity_kwp or 0
		row.cost_per_kwp = round(row.total_cost / size, 2) if size else None

	columns = [
		{"fieldname": "name", "label": "BOQ", "fieldtype": "Link", "options": "FC BOQ", "width": 150},
		{"fieldname": "title", "label": "Job", "fieldtype": "Data", "width": 200},
		{"fieldname": "project_key", "label": "Code", "fieldtype": "Data", "width": 110},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"fieldname": "contract_model", "label": "Model", "fieldtype": "Data", "width": 70},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 90},
		{"fieldname": "revision", "label": "Rev", "fieldtype": "Int", "width": 50},
		{"fieldname": "line_count", "label": "Lines", "fieldtype": "Int", "width": 60},
		{"fieldname": "capacity_kwp", "label": "kWp", "fieldtype": "Float", "width": 80},
		{"fieldname": "storage_kwh", "label": "kWh", "fieldtype": "Float", "width": 80},
		{"fieldname": "total_cost", "label": "Budget (Cost)", "fieldtype": "Currency", "width": 130},
		{"fieldname": "contract_value", "label": "Contract Value", "fieldtype": "Currency", "width": 130},
		{"fieldname": "gross_margin", "label": "Margin", "fieldtype": "Currency", "width": 120},
		{"fieldname": "gross_margin_percent", "label": "Margin %", "fieldtype": "Percent", "width": 80},
		{"fieldname": "cost_per_kwp", "label": "Cost / kWp", "fieldtype": "Currency", "width": 100},
		{"fieldname": "material_cost", "label": "Material", "fieldtype": "Currency", "width": 120},
		{"fieldname": "labour_cost", "label": "Labour", "fieldtype": "Currency", "width": 110},
		{"fieldname": "plant_cost", "label": "Plant", "fieldtype": "Currency", "width": 110},
		{"fieldname": "subcontract_cost", "label": "Subcontract", "fieldtype": "Currency", "width": 120},
		{"fieldname": "overhead_cost", "label": "Overhead", "fieldtype": "Currency", "width": 110},
	]
	return columns, rows
