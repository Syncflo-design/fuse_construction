"""Subcontract Status — value, certified, paid, retention and advance, one line per subcontract."""

import frappe
from frappe.utils import flt

from fuse_construction import maths


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"docstatus": 1}
	for field in ("project", "supplier", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)

	rows = []
	for sub in frappe.get_all(
		"FC Subcontract",
		filters=conditions,
		fields=["name", "title", "supplier", "supplier_name", "project", "status", "subcontract_value",
			"certified_to_date", "percent_certified", "contra_to_date", "retention_held", "retention_released",
			"retention_outstanding", "advance_amount", "advance_paid", "advance_recovered", "advance_outstanding",
			"remaining_to_certify", "certificate_count"],
		order_by="project asc, title asc",
	):
		paid = frappe.get_all(
			"FC Subcontract Certificate",
			filters={"subcontract": sub.name, "docstatus": 1, "intacct_status": "Paid"},
			pluck="net_payable",
		)
		paid += frappe.get_all(
			"FC Retention Release",
			filters={"subcontract": sub.name, "docstatus": 1, "intacct_status": "Paid"},
			pluck="release_amount",
		)
		sub.paid = maths.money(sum(flt(p) for p in paid))
		rows.append(sub)

	columns = [
		{"fieldname": "name", "label": "Subcontract", "fieldtype": "Link", "options": "FC Subcontract", "width": 150},
		{"fieldname": "title", "label": "Description", "fieldtype": "Data", "width": 200},
		{"fieldname": "supplier_name", "label": "Subcontractor", "fieldtype": "Data", "width": 170},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
		{"fieldname": "subcontract_value", "label": "Value", "fieldtype": "Currency", "width": 120},
		{"fieldname": "certified_to_date", "label": "Certified", "fieldtype": "Currency", "width": 120},
		{"fieldname": "percent_certified", "label": "% Certified", "fieldtype": "Percent", "width": 90},
		{"fieldname": "remaining_to_certify", "label": "Still to Certify", "fieldtype": "Currency", "width": 120},
		{"fieldname": "contra_to_date", "label": "Contra-charges", "fieldtype": "Currency", "width": 110},
		{"fieldname": "retention_held", "label": "Retention Held", "fieldtype": "Currency", "width": 120},
		{"fieldname": "retention_released", "label": "Retention Released", "fieldtype": "Currency", "width": 130},
		{"fieldname": "retention_outstanding", "label": "Retention Outstanding", "fieldtype": "Currency", "width": 140},
		{"fieldname": "advance_paid", "label": "Advance Paid", "fieldtype": "Currency", "width": 110},
		{"fieldname": "advance_outstanding", "label": "Advance Outstanding", "fieldtype": "Currency", "width": 140},
		{"fieldname": "paid", "label": "Paid (Intacct)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "certificate_count", "label": "Certificates", "fieldtype": "Int", "width": 90},
	]
	return columns, rows
