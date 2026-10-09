"""Tender Summary — every tender, its bids and who won it.

Adapted from epcforge's Tender Summary (MIT, Invento Software Limited).
"""

import frappe
from frappe.query_builder import Order
from frappe.query_builder.functions import Count


def execute(filters=None):
	filters = frappe._dict(filters or {})
	tender = frappe.qb.DocType("FC Tender")
	bidder = frappe.qb.DocType("FC Tender Bidder")
	bids = (
		frappe.qb.from_(bidder)
		.select(Count("*"))
		.where((bidder.parent == tender.name) & (bidder.parenttype == "FC Tender"))
	)

	query = (
		frappe.qb.from_(tender)
		.select(
			tender.name,
			tender.tender_title,
			tender.project,
			tender.boq_group,
			tender.package_type,
			tender.status,
			tender.submission_deadline,
			tender.estimated_value,
			bids.as_("bidders"),
			tender.quotes_received,
			tender.lowest_bidder,
			tender.lowest_bid_amount,
			tender.awarded_to,
			tender.award_amount,
		)
		.where(tender.docstatus < 2)
		.orderby(tender.submission_deadline, order=Order.desc)
	)
	for field in ("project", "status", "package_type"):
		if filters.get(field):
			query = query.where(tender[field] == filters.get(field))
	if filters.from_date:
		query = query.where(tender.submission_deadline >= filters.from_date)
	if filters.to_date:
		query = query.where(tender.submission_deadline <= filters.to_date)
	rows = query.run(as_dict=True)
	for row in rows:
		if row.award_amount and row.estimated_value:
			row.against_estimate = round((row.award_amount - row.estimated_value) / row.estimated_value * 100, 2)

	columns = [
		{"fieldname": "name", "label": "Tender", "fieldtype": "Link", "options": "FC Tender", "width": 150},
		{"fieldname": "tender_title", "label": "Title", "fieldtype": "Data", "width": 220},
		{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 120},
		{"fieldname": "boq_group", "label": "Package", "fieldtype": "Data", "width": 160},
		{"fieldname": "package_type", "label": "Type", "fieldtype": "Data", "width": 100},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
		{"fieldname": "submission_deadline", "label": "Deadline", "fieldtype": "Datetime", "width": 150},
		{"fieldname": "estimated_value", "label": "Estimate", "fieldtype": "Currency", "width": 120},
		{"fieldname": "bidders", "label": "Invited", "fieldtype": "Int", "width": 70},
		{"fieldname": "quotes_received", "label": "Bids", "fieldtype": "Int", "width": 60},
		{"fieldname": "lowest_bidder", "label": "Lowest Compliant", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"fieldname": "lowest_bid_amount", "label": "Lowest Bid", "fieldtype": "Currency", "width": 120},
		{"fieldname": "awarded_to", "label": "Awarded To", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"fieldname": "award_amount", "label": "Award", "fieldtype": "Currency", "width": 120},
		{"fieldname": "against_estimate", "label": "vs Estimate %", "fieldtype": "Percent", "width": 100},
	]
	return columns, rows
