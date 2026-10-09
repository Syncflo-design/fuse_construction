"""What has already happened on a subcontract — shared by the subcontract, its certificates
and its retention releases, so all three read history the same way.

Only SUBMITTED documents count. A draft certificate is an assessment in progress; letting it
move another certificate's "previously certified" would make two drafts depend on the order
they happen to be saved in.
"""

import frappe
from frappe.model.workflow import get_workflow_name
from frappe.utils import flt

from fuse_construction import maths

CERTIFICATE = "FC Subcontract Certificate"


def certificate_history(subcontract, exclude=None):
	"""Running totals from every submitted certificate on a subcontract."""
	certs = frappe.get_all(
		CERTIFICATE,
		filters={"subcontract": subcontract, "docstatus": 1, "name": ["!=", exclude or ""]},
		fields=[
			"name", "certificate_type", "certificate_no", "gross_to_date", "gross_this_certificate",
			"retention_this", "advance_recovery_this", "contra_total", "net_payable",
		],
		order_by="certificate_no desc",
	)
	progress = [c for c in certs if c.certificate_type == "Progress"]
	last = progress[0] if progress else None

	last_lines = {}
	if last:
		for line in frappe.get_all(
			"FC Certificate Line",
			filters={"parent": last.name, "parenttype": CERTIFICATE},
			fields=["subcontract_line", "to_date_qty", "to_date_amount"],
		):
			last_lines[line.subcontract_line] = (flt(line.to_date_qty), flt(line.to_date_amount))

	return frappe._dict(
		count=len(certs),
		last_no=max((c.certificate_no or 0 for c in certs), default=0),
		# Cumulative: the latest certificate's to-date IS everything certified before.
		certified=maths.money(last.gross_to_date) if last else 0.0,
		contra=maths.money(sum(flt(c.contra_total) for c in progress)),
		retention_held=maths.money(sum(flt(c.retention_this) for c in progress)),
		advance_recovered=maths.money(sum(flt(c.advance_recovery_this) for c in progress)),
		advance_paid=maths.money(
			sum(flt(c.net_payable) for c in certs if c.certificate_type == "Advance Payment")
		),
		last_lines=last_lines,
		certificates=certs,
	)


def released_retention(subcontract=None, boq=None, exclude=None):
	"""{stage row: (release, amount)} and the total, from submitted releases."""
	filters = {"docstatus": 1, "name": ["!=", exclude or ""]}
	if subcontract:
		filters.update(subcontract=subcontract, release_for="Subcontractor")
	else:
		filters.update(boq=boq, release_for="Client")
	releases = frappe.get_all(
		"FC Retention Release", filters=filters, fields=["name", "stage", "release_amount"]
	)
	by_stage = {r.stage: (r.name, flt(r.release_amount)) for r in releases if r.stage}
	return by_stage, maths.money(sum(flt(r.release_amount) for r in releases))


def workflow_active():
	"""Whether certificates are approved through a Frappe Workflow on this site."""
	return bool(get_workflow_name(CERTIFICATE))
