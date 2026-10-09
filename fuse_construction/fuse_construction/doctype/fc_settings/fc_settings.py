import frappe
from frappe.model.document import Document
from frappe.utils import flt

from fuse_construction import retention

# Every account a posting needs. Posting refuses to switch on until all are named, so the
# first certificate after switching it on cannot fail halfway for want of one.
POSTING_ACCOUNTS = {
	"subcontract_cost_account": "Subcontract Cost Account",
	"retention_payable_account": "Retention Payable Account",
	"subcontract_advance_account": "Subcontractor Advances Account",
	"revenue_account": "Contract Revenue Account",
	"retention_receivable_account": "Retention Receivable Account",
	"client_advance_account": "Client Advances Account",
}


class FCSettings(Document):
	def validate(self):
		retention.validate_shares(self.default_release_stages, "Default release stages")
		for field in ("overtime_multiplier", "sunday_multiplier", "standard_day_hours"):
			if flt(self.get(field)) < 0:
				frappe.throw(f"{self.meta.get_label(field)} cannot be negative.")
		if self.post_to_intacct:
			missing = [label for field, label in POSTING_ACCOUNTS.items() if not self.get(field)]
			if missing:
				frappe.throw(
					"Posting to Intacct needs every account set first. Missing: " + ", ".join(missing),
					title="Accounts not set",
				)
		if self.create_subcontract_purchase_order and self.subcontract_item:
			if frappe.db.get_value("Item", self.subcontract_item, "is_stock_item"):
				frappe.throw("The subcontract item must be a non-stock item: a subcontract is a service.")

	def on_update(self):
		frappe.clear_document_cache("FC Settings", "FC Settings")
