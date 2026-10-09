"""Frappe CRM → construction: a deal marked Won opens the job.

Frappe CRM is optional. Nothing here imports it, the hook on "CRM Deal" simply never fires
on a site without it, and the custom fields on CRM Deal are only created where the doctype
exists (install.py).

Won → a client (found by name, or created), a BOQ from the deal's template sized to the
plant on the deal, submitted and awarded — the project with a task per section — without
retyping anything. If any step fails, NONE of it is kept and the deal records why: a
salesperson closing a deal must never be blocked by a construction setting.

Phase 2: with Intacct posting on, the client is created in Intacct first (Intacct is the
customer master) and mirrored; until then it is created here.
"""

import frappe
from frappe.utils import flt, nowdate

from fuse_construction import commercial

WON = "Won"


def on_deal_update(doc, method=None):
	if doc.get("status") != WON or doc.get("fc_boq"):
		return
	if not doc.get("fc_template"):
		doc.add_comment("Comment", "Won — no construction template on the deal, so no BOQ was opened.")
		return

	frappe.db.savepoint("fc_deal_won")
	try:
		result = create_from_deal(doc)
	except Exception as exc:
		frappe.db.rollback(save_point="fc_deal_won")
		frappe.log_error(title=f"Fuse Construction: deal {doc.name} won, job not opened",
			message=frappe.get_traceback())
		doc.add_comment("Comment", f"Won — the construction job could not be opened: {frappe.utils.escape_html(str(exc))}")
		return
	doc.add_comment(
		"Comment",
		f"Won — BOQ {result['boq']} awarded as project {result['project']}, "
		f"{result['tasks']} sections.",
	)


def create_from_deal(deal):
	customer = _customer_for(deal)
	boq = frappe.new_doc("FC BOQ")
	boq.title = (deal.get("organization") or deal.get("lead_name") or deal.name)[:140]
	boq.contract_model = deal.get("fc_contract_model") or "EPC"
	boq.customer = customer if boq.contract_model == "EPC" else None
	boq.template = deal.get("fc_template")
	boq.capacity_kwp = flt(deal.get("fc_capacity_kwp"))
	boq.storage_kwh = flt(deal.get("fc_storage_kwh"))
	boq.start_date = nowdate()
	boq.crm_deal = deal.name
	boq.flags.ignore_permissions = True
	boq.insert(ignore_permissions=True)
	boq.submit()
	result = commercial.award(boq, ignore_permissions=True)
	frappe.db.set_value(deal.doctype, deal.name, {"fc_boq": boq.name, "fc_project": result["project"]},
		update_modified=False)
	return {"boq": boq.name, **result}


def _customer_for(deal):
	name = (deal.get("organization") or deal.get("lead_name") or "").strip()
	if not name:
		frappe.throw("The deal has no organisation to bill.")
	existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
	if existing:
		return existing
	customer = frappe.new_doc("Customer")
	customer.customer_name = name
	customer.customer_type = "Company"
	customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or frappe.get_all(
		"Customer Group", filters={"is_group": 0}, pluck="name", limit=1
	)[0]
	customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or frappe.get_all(
		"Territory", filters={"is_group": 0}, pluck="name", limit=1
	)[0]
	customer.insert(ignore_permissions=True)
	return customer.name


@frappe.whitelist()
def open_job(deal):
	"""Open the job from a deal by hand — for a deal won before its template was set."""
	doc = frappe.get_doc("CRM Deal", deal)
	doc.check_permission("write")
	frappe.has_permission("FC BOQ", "create", throw=True)
	if doc.get("fc_boq"):
		frappe.throw(f"This deal already opened {doc.fc_boq}.")
	if not doc.get("fc_template"):
		frappe.throw("Choose the construction template on the deal first.")
	return create_from_deal(doc)
