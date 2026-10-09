"""Frappe CRM → construction: price a deal while it is still being sold, open the job when won.

Frappe CRM is optional. Nothing here imports it: the hook on "CRM Deal" never fires on a site
without it, the custom fields and the deal's buttons are only created where it is installed
(install.py), and every CRM doctype is checked for before it is touched.

The flow, with the salesperson in CRM and the estimator in the desk:

  * Price this deal (a button on the deal) — a draft BOQ from the deal's template, sized to
    the plant on the deal, tied to the deal and with no client yet: a prospect is not a
    customer, and making one for every quote fills the customer list with people who never
    bought. The estimator prices it in the desk.
  * Quote this deal — a draft Quotation from that BOQ, addressed to the deal itself.
  * Won — the client is created (with the deal's contacts and the organisation's address),
    set on the BOQ, which is submitted and awarded: the project, a task per section, the
    budget. A deal won without being priced first gets its BOQ straight from the template.
    Draft quotations addressed to the deal are moved onto the client.

If the Won step fails, NONE of it is kept and the deal records why in a comment the
salesperson can see: closing a deal must never be blocked by a construction setting.

Phase 2: with Intacct posting on, the client is created in Intacct first (Intacct is the
customer master) and mirrored; until then it is created here.
"""

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from fuse_construction import commercial, settings

WON = "Won"
DEAL = "CRM Deal"


# ──────────────────────────────────────────────────────────────────────────────
# While the deal is being sold
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def price_deal(deal):
	"""The deal's draft BOQ — made now, or the one it already has.

	The salesperson asks for a price; the estimator gives it. So anyone who can work the deal
	may start the draft, whether or not they may edit BOQs: pricing it, and submitting it as
	the price, still takes the estimator's rights.
	"""
	doc = frappe.get_doc(DEAL, deal)
	doc.check_permission("write")
	if doc.get("fc_boq") and frappe.db.exists("FC BOQ", doc.fc_boq):
		return _boq_link(doc.fc_boq)

	template = doc.get("fc_template") or _only_template()
	if not template:
		frappe.throw("Choose the BOQ template on the deal first: there is more than one.")

	boq = frappe.new_doc("FC BOQ")
	_describe(boq, doc, template)
	# A client only if the organisation already is one — a repeat client is quoted as such.
	boq.customer = _existing_customer(doc) if boq.contract_model == "EPC" else None
	boq.flags.ignore_permissions = True
	boq.insert(ignore_permissions=True)
	frappe.db.set_value(DEAL, doc.name, "fc_boq", boq.name, update_modified=False)
	return _boq_link(boq.name)


@frappe.whitelist()
def quote_deal(deal, by="Section"):
	"""A draft Quotation from the deal's BOQ, addressed to the deal (or its client, if any).

	Only once the estimator has submitted the BOQ: a quotation from a draft would send the
	client a price nobody has finished."""
	doc = frappe.get_doc(DEAL, deal)
	doc.check_permission("write")
	frappe.has_permission("Quotation", "create", throw=True)
	if not (doc.get("fc_boq") and frappe.db.exists("FC BOQ", doc.fc_boq)):
		frappe.throw("Price the deal first: the quotation is made from its BOQ.")
	boq = frappe.get_doc("FC BOQ", doc.fc_boq)
	if boq.docstatus != 1:
		frappe.throw(f"{boq.name} is still being priced. The estimator submits it when the price is ready.")
	name = commercial.quotation_for(boq, by)
	return {"quotation": name, "url": f"/desk/quotation/{name}"}


def _boq_link(name):
	return {"boq": name, "url": f"/desk/fc-boq/{name}",
		"can_open": bool(frappe.has_permission("FC BOQ", "read", doc=name))}


def _only_template():
	templates = frappe.get_all("FC BOQ Template", pluck="name", limit=2)
	return templates[0] if len(templates) == 1 else None


def _describe(boq, deal, template):
	"""What a BOQ takes from its deal. No start date: that is set when the job is won."""
	boq.title = _client_name(deal)[:140]
	boq.contract_model = deal.get("fc_contract_model") or "EPC"
	boq.template = template
	boq.capacity_kwp = flt(deal.get("fc_capacity_kwp"))
	boq.storage_kwh = flt(deal.get("fc_storage_kwh"))
	boq.crm_deal = deal.name


# ──────────────────────────────────────────────────────────────────────────────
# Won
# ──────────────────────────────────────────────────────────────────────────────


def on_deal_update(doc, method=None):
	if doc.get("status") != WON or doc.get("fc_project"):
		return
	priced = doc.get("fc_boq") and frappe.db.exists("FC BOQ", doc.fc_boq)
	if not priced and not (doc.get("fc_template") or _only_template()):
		doc.add_comment("Comment", "Won — no construction template on the deal, so no job was opened.")
		return

	frappe.db.savepoint("fc_deal_won")
	try:
		result = award_priced(doc) if priced else create_from_deal(doc)
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


def award_priced(deal):
	"""The deal's own BOQ, priced while it was being sold: client set, submitted, awarded."""
	boq = frappe.get_doc("FC BOQ", deal.fc_boq)
	if boq.status == "Awarded":
		frappe.db.set_value(DEAL, deal.name, "fc_project", boq.project, update_modified=False)
		return {"boq": boq.name, "project": boq.project, "tasks": len(boq.sections)}
	customer = _customer_for(deal) if boq.contract_model == "EPC" else None
	if boq.docstatus == 0:
		boq.customer = customer or boq.customer
		boq.start_date = boq.start_date or _next_monday()
		boq.flags.ignore_permissions = True
		boq.submit()
	elif customer and not boq.customer:
		boq.db_set("customer", customer)
	return _award(deal, boq, customer)


def create_from_deal(deal):
	"""A deal won without being priced first: its BOQ straight from the template."""
	boq = frappe.new_doc("FC BOQ")
	_describe(boq, deal, deal.get("fc_template") or _only_template())
	customer = _customer_for(deal) if boq.contract_model == "EPC" else None
	boq.customer = customer if boq.contract_model == "EPC" else None
	boq.start_date = _next_monday()
	boq.flags.ignore_permissions = True
	boq.insert(ignore_permissions=True)
	boq.submit()
	return _award(deal, boq, customer)


def _award(deal, boq, customer):
	result = commercial.award(boq, ignore_permissions=True)
	frappe.db.set_value(DEAL, deal.name, {"fc_boq": boq.name, "fc_project": result["project"]},
		update_modified=False)
	if customer:
		_move_quotations(deal.name, customer)
	return {"boq": boq.name, **result}


def _next_monday():
	"""A won job starts next Monday: one starting today is behind its own programme by tonight."""
	today = getdate(nowdate())
	return add_days(today, 7 - today.weekday())


def _move_quotations(deal, customer):
	"""Draft quotations addressed to the deal now go to the client it became. A submitted one
	stays as it was sent."""
	for name in frappe.get_all(
		"Quotation", filters={"quotation_to": DEAL, "party_name": deal, "docstatus": 0}, pluck="name"
	):
		quotation = frappe.get_doc("Quotation", name)
		quotation.quotation_to = "Customer"
		quotation.party_name = customer
		quotation.flags.ignore_permissions = True
		quotation.save(ignore_permissions=True)


# ──────────────────────────────────────────────────────────────────────────────
# The client
# ──────────────────────────────────────────────────────────────────────────────


def _client_name(deal):
	return (deal.get("organization") or deal.get("lead_name") or deal.name or "").strip()


def _existing_customer(deal):
	name = _client_name(deal)
	return frappe.db.get_value("Customer", {"customer_name": name}, "name") if name else None


def _customer_for(deal):
	"""The deal's client: found by name, or created with its contacts and address."""
	name = _client_name(deal)
	if not name:
		frappe.throw("The deal has no organisation to bill.")
	existing = _existing_customer(deal)
	if existing:
		_link_people(deal, existing)
		return existing

	customer = frappe.new_doc("Customer")
	customer.customer_name = name
	customer.customer_type = "Company" if deal.get("organization") else "Individual"
	customer.customer_group = (
		settings.get("won_deal_customer_group")
		or frappe.db.get_single_value("Selling Settings", "customer_group")
		or frappe.get_all("Customer Group", filters={"is_group": 0}, pluck="name", limit=1)[0]
	)
	customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or frappe.get_all(
		"Territory", filters={"is_group": 0}, pluck="name", limit=1
	)[0]
	if deal.get("currency"):
		customer.default_currency = deal.currency
	if deal.get("website"):
		customer.website = deal.website
	customer.insert(ignore_permissions=True)
	_link_people(deal, customer.name)
	return customer.name


def _link_people(deal, customer):
	"""The deal's contacts and its organisation's address, linked to the client.

	CRM keeps them as ordinary Contact and Address records, so they are linked, not copied:
	one person, one record, whichever side edits it. The primary ones become the client's.
	"""
	contacts = [row.contact for row in deal.get("contacts") or [] if row.get("contact")]
	primary = next((row.contact for row in deal.get("contacts") or [] if row.get("is_primary")), None)
	if deal.get("contact") and deal.contact not in contacts:
		contacts.append(deal.contact)
	for contact in contacts:
		_link("Contact", contact, customer)

	address = None
	if deal.get("organization") and frappe.db.exists("DocType", "CRM Organization"):
		address = frappe.db.get_value("CRM Organization", deal.organization, "address")
		if address:
			_link("Address", address, customer)

	updates = {}
	if (primary or (contacts[0] if contacts else None)) and not frappe.db.get_value(
		"Customer", customer, "customer_primary_contact"
	):
		updates["customer_primary_contact"] = primary or contacts[0]
	if address and not frappe.db.get_value("Customer", customer, "customer_primary_address"):
		updates["customer_primary_address"] = address
	if updates:
		customer_doc = frappe.get_doc("Customer", customer)
		customer_doc.update(updates)
		customer_doc.flags.ignore_permissions = True
		customer_doc.save(ignore_permissions=True)


def _link(doctype, name, customer):
	if not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	if any(link.link_doctype == "Customer" and link.link_name == customer for link in doc.get("links") or []):
		return
	doc.append("links", {"link_doctype": "Customer", "link_name": customer})
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def open_job(deal):
	"""Open the job from a deal by hand — for a deal won before its template was set."""
	doc = frappe.get_doc(DEAL, deal)
	doc.check_permission("write")
	frappe.has_permission("FC BOQ", "submit", throw=True)
	if doc.get("fc_project"):
		frappe.throw(f"This deal already opened {doc.fc_project}.")
	priced = doc.get("fc_boq") and frappe.db.exists("FC BOQ", doc.fc_boq)
	if not priced and not (doc.get("fc_template") or _only_template()):
		frappe.throw("Choose the construction template on the deal first.")
	return award_priced(doc) if priced else create_from_deal(doc)
