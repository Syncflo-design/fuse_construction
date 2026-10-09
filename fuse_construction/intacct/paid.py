"""Nightly: which posted bills and invoices Intacct has paid.

Read-only against Intacct. Marks the certificate / valuation / release Paid and its payment
schedule row with it, so the subcontract shows what has actually left the bank.

STATUS: phase 2, and the field names (STATE, WHENPAID) are not yet confirmed with
gateway.lookup on a live company. The job stands down silently while posting is off.
"""

import frappe
from frappe.utils import getdate

from fuse_construction import settings
from fuse_construction.intacct import posting

SOURCES = (
	("FC Subcontract Certificate", "APBILL"),
	("FC Retention Release", "APBILL"),
	("FC Client Valuation", "ARINVOICE"),
)


def scheduled():
	if not settings.intacct_posting_on():
		return
	for doctype, intacct_object in SOURCES:
		try:
			_mark_paid(doctype, intacct_object)
		except Exception:
			frappe.log_error(title=f"FC paid status: {doctype}", message=frappe.get_traceback())


def _mark_paid(doctype, intacct_object):
	gw = posting.gateway()
	open_docs = frappe.get_all(
		doctype, filters={"docstatus": 1, "intacct_status": "Posted", "intacct_key": ["is", "set"]},
		fields=["name", "intacct_key"],
	)
	for chunk in range(0, len(open_docs), 100):
		batch = open_docs[chunk : chunk + 100]
		values = "".join(f"<value>{frappe.utils.escape_html(d.intacct_key)}</value>" for d in batch)
		rows = gw.query(
			intacct_object,
			["RECORDNO", "STATE", "WHENPAID"],
			filter_xml=f"<in><field>RECORDNO</field>{values}</in>",
		)
		paid = {gw.val(r, "RECORDNO"): gw.val(r, "WHENPAID") for r in rows if (gw.val(r, "STATE") or "").lower() == "paid"}
		for doc in batch:
			if doc.intacct_key in paid:
				# An unparseable date stays empty rather than becoming today: getdate(None) is
				# today, which would invent a payment date nobody reported.
				iso = iso_date(paid[doc.intacct_key])
				frappe.db.set_value(
					doctype, doc.name,
					{"intacct_status": "Paid", "paid_on": getdate(iso) if iso else None},
					update_modified=False,
				)
				if doctype == "FC Subcontract Certificate":
					row = frappe.db.get_value(doctype, doc.name, "schedule_row")
					if row:
						frappe.db.set_value("FC Subcontract Payment Schedule", row, "status", "Paid",
							update_modified=False)
		frappe.db.commit()


def iso_date(value):
	"""Intacct's MM/DD/YYYY to ISO, via fuse_core's parser — never the local reading."""
	from fuse_core.rules import intacct_date

	return intacct_date(value)
