"""Certificates, valuations and retention releases → Intacct AP bills and AR invoices.

Intacct first, as everywhere in Fuse: the posting happens before the document's local
status moves, and a rejection raises — rolling the local change back with it.

Every amount goes on its own line so Intacct carries the same story the certificate does:

  Subcontract certificate (AP bill)      gross → Subcontract Cost (on the project)
                                         contra → Subcontract Cost, negative (on the project)
                                         retention → Retention Payable, negative
                                         advance recovered → Subcontractor Advances, negative
  Advance payment (AP bill)              advance → Subcontractor Advances
  Client valuation (AR invoice)          gross → Contract Revenue (on the project)
                                         retention → Retention Receivable, negative
                                         advance recovered → Client Advances, negative
  Client advance (AR invoice)            advance → Client Advances
  Retention release, sub (AP bill)       amount → Retention Payable
  Retention release, client (AR invoice) amount → Retention Receivable

Retention is a line to a balance-sheet account rather than Intacct retainage: retainage is
per-company AP/AR configuration, a negative line to a liability posts the same way in every
company.

STATUS: the certificate and valuation shapes are fuse_projects 0.2.0's (d7eb39c), built
against leadertread-DEV. The advance and release lines are new. Prove every shape with
gateway.lookup and a test company BEFORE switching posting on (FC Settings) — the build
plan's rule, and the reason the switch is off.
"""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import frappe
from frappe.utils import add_days, cint, flt, getdate, now

from fuse_construction import settings

# ──────────────────────────────────────────────────────────────────────────────
# Shared with award.py and paid.py. Lifted from fuse_projects.commercial at 0.2.0 (d7eb39c,
# Syncflo), where these were built against leadertread-DEV.
# ──────────────────────────────────────────────────────────────────────────────


def gateway():
	from fuse_core import gateway as fuse_gateway

	return fuse_gateway


def text(parent, tag, value):
	element = ET.SubElement(parent, tag)
	element.text = str(value)
	return element


def us_date(value):
	"""The generic API reads MM/DD/YYYY whatever the company's locale."""
	return getdate(value).strftime("%m/%d/%Y")


def legacy_date(parent, tag, value):
	day = getdate(value)
	element = ET.SubElement(parent, tag)
	text(element, "year", day.year)
	text(element, "month", f"{day.month:02d}")
	text(element, "day", f"{day.day:02d}")
	return element


def money(value):
	return f"{flt(value, 2):.2f}"


def create_function(object_name, values):
	"""A generic `<create><OBJECT>` with flat fields, in the order given."""
	function = ET.Element("function")
	record = ET.SubElement(ET.SubElement(function, "create"), object_name)
	for tag, value in values.items():
		if value not in (None, ""):
			text(record, tag, value)
	return function


def find_one(object_name, fields, field, value):
	rows = gateway().query(
		object_name,
		fields,
		filter_xml=f"<equalto><field>{field}</field><value>{escape(str(value))}</value></equalto>",
		page_size=10,
	)
	return rows[0] if rows else None


def forget_last_message():
	"""Drop the error dialog a rejected attempt queued — the next shape may be accepted."""
	log = getattr(frappe.local, "message_log", None)
	if log:
		log.pop()


def post_first_accepted(attempts, reference):
	"""Post the first of several equivalent shapes Intacct accepts.

	Only a REJECTION moves on to the next shape. A timeout is ambiguous — Intacct may have
	committed — so it is raised at once rather than risking the same bill twice.
	"""
	errors = []
	for purpose, build in attempts:
		try:
			return gateway().execute_many(build(), reference=reference, purpose=purpose)
		except Exception as exc:
			message = str(exc)
			if "Intacct rejected the request" not in message:
				raise
			errors.append(message.replace("Intacct rejected the request:", "").strip())
			forget_last_message()
	frappe.throw("Intacct refused this posting:\n\n" + "\n\n".join(errors), title="Intacct refused it")


def stamped(doc, purpose):
	"""A control-ID purpose unique to this document's life on this site.

	The name alone is not enough on a demo site: restoring a backup winds the naming series
	back, so the next document would carry a control ID Intacct has already taken. The
	creation time differs; a retry of the same document keeps it.
	"""
	return f"{purpose}:{doc.creation}"


def intacct_id(doctype, name, fieldname, label):
	"""An Intacct ID another Fuse app keeps on a master. Refuses rather than guesses."""
	if not frappe.get_meta(doctype).has_field(fieldname):
		frappe.throw(
			f"{doctype} has no {fieldname} field on this site, so {label} cannot be matched to Intacct. "
			"Install the Fuse app that syncs it, or keep posting switched off."
		)
	value = frappe.db.get_value(doctype, name, fieldname)
	if not value:
		frappe.throw(
			f"{name} has no Intacct ID. {label} come from Intacct — a posting for one it has never heard "
			"of is stopped, not guessed."
		)
	return value


def project_id(project, boq=None):
	value = (boq.intacct_project_id if boq else None) or (
		frappe.db.get_value("Project", project, "custom_intacct_project_id")
		if frappe.get_meta("Project").has_field("custom_intacct_project_id")
		else None
	)
	if not value:
		frappe.throw(f"{project} is not an Intacct project. Award its BOQ with posting on, or sync it from Intacct.")
	return value


def location(company):
	return gateway().entity_for_company(company)


def _account(field):
	value = settings.get(field)
	if not value:
		frappe.throw(f"Set {frappe.get_meta('FC Settings').get_label(field)} in FC Settings before posting.")
	return value


def _line(account, amount, memo, project=None):
	return {"account": account, "amount": flt(amount, 2), "memo": memo, "project": project}


# ──────────────────────────────────────────────────────────────────────────────
# Shapes
# ──────────────────────────────────────────────────────────────────────────────


def build_bill_xml(*, vendor_id, posting_date, due_date, bill_no, description, lines, location_id):
	"""Generic `<create><APBILL>`."""
	function = ET.Element("function")
	bill = ET.SubElement(ET.SubElement(function, "create"), "APBILL")
	text(bill, "VENDORID", vendor_id)
	text(bill, "WHENCREATED", us_date(posting_date))
	text(bill, "WHENDUE", us_date(due_date))
	text(bill, "RECORDID", bill_no)
	text(bill, "DESCRIPTION", description)
	items = ET.SubElement(bill, "APBILLITEMS")
	for line in lines:
		item = ET.SubElement(items, "APBILLITEM")
		text(item, "ACCOUNTNO", line["account"])
		text(item, "TRX_AMOUNT", money(line["amount"]))
		text(item, "ENTRYDESCRIPTION", line["memo"])
		if location_id:
			text(item, "LOCATIONID", location_id)
		if line["project"]:
			text(item, "PROJECTID", line["project"])
	return function


def build_bill_legacy_xml(*, vendor_id, posting_date, due_date, bill_no, description, lines, location_id):
	"""Legacy `<create_bill>`, for a company whose AP refuses the generic shape. Order matters."""
	function = ET.Element("function")
	bill = ET.SubElement(function, "create_bill")
	text(bill, "vendorid", vendor_id)
	legacy_date(bill, "datecreated", posting_date)
	legacy_date(bill, "datedue", due_date)
	text(bill, "billno", bill_no)
	text(bill, "description", description)
	items = ET.SubElement(bill, "billitems")
	for line in lines:
		item = ET.SubElement(items, "lineitem")
		text(item, "glaccountno", line["account"])
		text(item, "amount", money(line["amount"]))
		text(item, "memo", line["memo"])
		if location_id:
			text(item, "locationid", location_id)
		if line["project"]:
			text(item, "projectid", line["project"])
	return function


def build_invoice_xml(*, customer_id, posting_date, due_date, description, lines, location_id):
	"""Generic `<create><ARINVOICE>`. No invoice number — AR numbering is Intacct's."""
	function = ET.Element("function")
	invoice = ET.SubElement(ET.SubElement(function, "create"), "ARINVOICE")
	text(invoice, "CUSTOMERID", customer_id)
	text(invoice, "WHENCREATED", us_date(posting_date))
	text(invoice, "WHENDUE", us_date(due_date))
	text(invoice, "DESCRIPTION", description)
	items = ET.SubElement(invoice, "ARINVOICEITEMS")
	for line in lines:
		item = ET.SubElement(items, "ARINVOICEITEM")
		text(item, "ACCOUNTNO", line["account"])
		text(item, "TRX_AMOUNT", money(line["amount"]))
		text(item, "ENTRYDESCRIPTION", line["memo"])
		if location_id:
			text(item, "LOCATIONID", location_id)
		if line["project"]:
			text(item, "PROJECTID", line["project"])
	return function


def build_invoice_legacy_xml(*, customer_id, posting_date, due_date, description, lines, location_id):
	"""Legacy `<create_invoice>`. Order matters."""
	function = ET.Element("function")
	invoice = ET.SubElement(function, "create_invoice")
	text(invoice, "customerid", customer_id)
	legacy_date(invoice, "datecreated", posting_date)
	legacy_date(invoice, "datedue", due_date)
	text(invoice, "description", description)
	items = ET.SubElement(invoice, "invoiceitems")
	for line in lines:
		item = ET.SubElement(items, "lineitem")
		text(item, "glaccountno", line["account"])
		text(item, "amount", money(line["amount"]))
		text(item, "memo", line["memo"])
		if location_id:
			text(item, "locationid", location_id)
		if line["project"]:
			text(item, "projectid", line["project"])
	return function


# ──────────────────────────────────────────────────────────────────────────────
# What each document posts
# ──────────────────────────────────────────────────────────────────────────────


def certificate_shape(cert):
	boq = frappe.get_doc("FC BOQ", cert.boq) if cert.boq else None
	project = project_id(cert.project, boq)
	vendor_id = intacct_id("Supplier", cert.supplier, "custom_intacct_vendor_id", "Subcontractors")
	if cert.certificate_type == "Advance Payment":
		lines = [_line(_account("subcontract_advance_account"), cert.net_payable,
			f"Advance on {cert.subcontract}")]
		description = f"Subcontract advance {cert.name}, {cert.subcontract}"
	else:
		lines = [_line(_account("subcontract_cost_account"), cert.gross_this_certificate,
			f"Cert {cert.certificate_no}: work certified", project)]
		for contra in cert.contra_charges:
			lines.append(_line(_account("subcontract_cost_account"), -flt(contra.amount),
				f"Contra-charge: {contra.description}", project))
		if flt(cert.retention_this):
			lines.append(_line(_account("retention_payable_account"), -flt(cert.retention_this),
				f"Retention {flt(cert.retention_percent):g}% held"))
		if flt(cert.advance_recovery_this):
			lines.append(_line(_account("subcontract_advance_account"), -flt(cert.advance_recovery_this),
				"Advance recovered"))
		description = f"Subcontract certificate {cert.certificate_no}, {cert.subcontract}"
	return {
		"vendor_id": vendor_id,
		"posting_date": cert.posting_date,
		"due_date": cert.due_date or add_days(cert.posting_date, cint(settings.get("payment_terms_days"))),
		"bill_no": cert.name,
		"description": description[:400],
		"lines": lines,
		"location_id": location(cert.company),
	}


def valuation_shape(valuation):
	boq = frappe.get_doc("FC BOQ", valuation.boq)
	project = project_id(valuation.project, boq)
	customer_id = intacct_id("Customer", valuation.customer, "custom_intacct_customer_id", "Clients")
	if valuation.valuation_type == "Advance":
		lines = [_line(_account("client_advance_account"), valuation.advance_amount, f"Advance on {boq.title}")]
	else:
		lines = [_line(_account("revenue_account"), valuation.gross_this_valuation,
			f"Valuation {valuation.valuation_no}, {valuation.period or 'work to date'}", project)]
		if flt(valuation.retention_this):
			lines.append(_line(_account("retention_receivable_account"), -flt(valuation.retention_this),
				f"Retention {flt(valuation.retention_percent):g}% held by client"))
		if flt(valuation.advance_recovery_this):
			lines.append(_line(_account("client_advance_account"), -flt(valuation.advance_recovery_this),
				"Advance recovered"))
	return {
		"customer_id": customer_id,
		"posting_date": valuation.posting_date,
		"due_date": valuation.due_date or valuation.posting_date,
		"description": f"Valuation {valuation.name}, {project}, {valuation.period or ''}".strip(" ,")[:400],
		"lines": lines,
		"location_id": location(valuation.company),
	}


def release_shape(release):
	if release.release_for == "Subcontractor":
		return "bill", {
			"vendor_id": intacct_id("Supplier", release.supplier, "custom_intacct_vendor_id", "Subcontractors"),
			"posting_date": release.posting_date,
			"due_date": release.posting_date,
			"bill_no": release.name,
			"description": f"Retention release: {release.stage_name}, {release.subcontract}"[:400],
			"lines": [_line(_account("retention_payable_account"), release.release_amount,
				f"Retention released: {release.stage_name}")],
			"location_id": location(release.company),
		}
	return "invoice", {
		"customer_id": intacct_id("Customer", release.customer, "custom_intacct_customer_id", "Clients"),
		"posting_date": release.posting_date,
		"due_date": release.posting_date,
		"description": f"Retention release: {release.stage_name}, {release.boq}"[:400],
		"lines": [_line(_account("retention_receivable_account"), release.release_amount,
			f"Retention released: {release.stage_name}")],
		"location_id": location(release.company),
	}


# ──────────────────────────────────────────────────────────────────────────────
# Posting
# ──────────────────────────────────────────────────────────────────────────────


def _bill(doc, shape, purpose):
	return post_first_accepted(
		[
			(stamped(doc, purpose), lambda: [build_bill_xml(**shape)]),
			(stamped(doc, f"{purpose}_legacy"), lambda: [build_bill_legacy_xml(**shape)]),
		],
		(doc.doctype, doc.name),
	)


def _invoice(doc, shape, purpose):
	return post_first_accepted(
		[
			(stamped(doc, purpose), lambda: [build_invoice_xml(**shape)]),
			(stamped(doc, f"{purpose}_legacy"), lambda: [build_invoice_legacy_xml(**shape)]),
		],
		(doc.doctype, doc.name),
	)


def _record(doc, keys):
	doc.db_set(
		{"intacct_key": keys[0] if keys else None, "intacct_posted_on": now(), "intacct_status": "Posted",
			"intacct_error": None},
		update_modified=False,
	)
	return keys[0] if keys else None


def post_certificate(cert):
	if cert.get("intacct_key"):
		return cert.intacct_key
	return _record(cert, _bill(cert, certificate_shape(cert), "fc_certificate"))


def post_valuation(valuation):
	if valuation.get("intacct_key"):
		return valuation.intacct_key
	return _record(valuation, _invoice(valuation, valuation_shape(valuation), "fc_valuation"))


def post_release(release):
	if release.get("intacct_key"):
		return release.intacct_key
	kind, shape = release_shape(release)
	keys = _bill(release, shape, "fc_release") if kind == "bill" else _invoice(release, shape, "fc_release")
	return _record(release, keys)


@frappe.whitelist()
def preview_posting(doctype, name):
	"""The XML a document would send, without sending it. System Manager only."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc(doctype, name)
	if doctype == "FC Subcontract Certificate":
		return ET.tostring(build_bill_xml(**certificate_shape(doc)), encoding="unicode")
	if doctype == "FC Client Valuation":
		return ET.tostring(build_invoice_xml(**valuation_shape(doc)), encoding="unicode")
	if doctype == "FC Retention Release":
		kind, shape = release_shape(doc)
		builder = build_bill_xml if kind == "bill" else build_invoice_xml
		return ET.tostring(builder(**shape), encoding="unicode")
	frappe.throw(f"Nothing to preview for {doctype}.")
