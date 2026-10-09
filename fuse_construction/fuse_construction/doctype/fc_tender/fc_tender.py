"""Outbound tender: choosing who builds or supplies a package.

Draft → Published (submit) → Under Evaluation → Awarded / Cancelled. Bids are recorded on
the published tender; the award (fuse_construction.commercial.award_tender) turns the chosen
bid into a draft subcontract or purchase order.

Adapted from epcforge's Tender (MIT, Invento Software Limited).
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from fuse_construction import maths


class FCTender(Document):
	def validate(self):
		for row in self.items:
			row.estimated_amount = maths.money(flt(row.qty) * flt(row.estimated_rate))
		if self.items:
			self.estimated_value = maths.money(sum(flt(row.estimated_amount) for row in self.items))
		self._count_bids()

	def before_update_after_submit(self):
		self._count_bids()

	def _count_bids(self):
		suppliers = [row.supplier for row in self.bidders]
		if len(suppliers) != len(set(suppliers)):
			frappe.throw("A bidder appears twice.")
		received = [
			row for row in self.bidders
			if flt(row.bid_amount) > 0 and row.bid_status not in ("Invited", "Declined")
		]
		self.bidder_count = len(self.bidders)
		self.quotes_received = len(received)
		# Lowest COMPLIANT bid: a cheap bid that fails the compliance check is not the one
		# anyone can award, so it is not the benchmark either.
		compliant = [row for row in received if row.technically_compliant] or received
		lowest = min(compliant, key=lambda row: flt(row.bid_amount), default=None)
		self.lowest_bidder = lowest.supplier if lowest else None
		self.lowest_bid_amount = flt(lowest.bid_amount) if lowest else 0

	def before_submit(self):
		if not self.bidders:
			frappe.throw("Invite at least one bidder before publishing.")
		self.status = "Published"

	def on_cancel(self):
		self.db_set("status", "Cancelled")
