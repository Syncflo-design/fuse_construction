"""FC Settings, read the same way everywhere.

One place that knows the defaults, so a site whose settings were never saved behaves the
same as one where somebody opened the page and pressed Save.
"""

import frappe
from frappe.utils import cint, flt

DEFAULTS = {
	"project_code_series": "FCP-.#####",
	"boq_markup_percent": 15,
	"payment_terms_days": 30,
	"sub_retention_percent": 5,
	"sub_retention_cap_percent": 5,
	"sub_advance_percent": 0,
	"sub_advance_recovery_percent": 20,
	"client_retention_percent": 5,
	"client_retention_cap_percent": 5,
	"client_advance_percent": 0,
	"dlp_months": 12,
	"day_start_time": "07:00:00",
	"standard_day_hours": 8,
	"auto_overtime": 1,
	"overtime_multiplier": 1.5,
	"sunday_multiplier": 2,
	"approver_role": "Projects Manager",
	"create_subcontract_purchase_order": 1,
	"retention_notify_role": "Projects Manager",
	"retention_notice_days": 14,
	"post_to_intacct": 0,
}

# The staggered release most South African subcontracts carry. Used until a site sets its own.
DEFAULT_STAGES = [
	{"stage_name": "Practical completion", "share_percent": 50, "trigger": "Practical Completion"},
	{
		"stage_name": "End of defects liability",
		"share_percent": 50,
		"trigger": "Months after Practical Completion",
		"months_after": 12,
	},
]


def doc():
	return frappe.get_cached_doc("FC Settings")


def get(fieldname):
	"""A setting, or its default when it has never been set.

	Checks and zeroes are real answers — "no overtime", "no cap" — so only None and "" fall
	back. A blank Data field means nobody chose.
	"""
	value = doc().get(fieldname)
	if value is None or value == "":
		return DEFAULTS.get(fieldname)
	return value


def number(fieldname):
	return flt(get(fieldname))


def flag(fieldname):
	return bool(cint(get(fieldname)))


def company(preferred=None):
	"""The company a new document belongs to when nothing more specific says."""
	return (
		preferred
		or get("default_company")
		or frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
	)


def release_stages():
	"""The default release stages, as plain dicts ready to append to a document."""
	rows = [
		{
			"stage_name": row.stage_name,
			"share_percent": row.share_percent,
			"trigger": row.trigger,
			"months_after": row.months_after,
		}
		for row in doc().get("default_release_stages") or []
	]
	if not rows:
		rows = [dict(row) for row in DEFAULT_STAGES]
		dlp = cint(get("dlp_months"))
		for row in rows:
			if row["trigger"] == "Months after Practical Completion":
				row["months_after"] = dlp
	return rows


def intacct_posting_on():
	"""Whether construction documents post to Intacct at all.

	Two switches, both required: this app's own, which is OFF until someone deliberately
	turns it on, and the Intacct connection itself. Read without touching the gateway, so
	asking the question never opens a session.
	"""
	if not flag("post_to_intacct"):
		return False
	if not frappe.db.exists("DocType", "Intacct Settings"):
		return False
	return bool(frappe.db.get_single_value("Intacct Settings", "enabled"))
