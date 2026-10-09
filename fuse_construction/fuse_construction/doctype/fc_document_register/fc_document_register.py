"""The project's document register: drawings, method statements, RFIs, NCRs and the rest.

Submitting issues a document. A new revision is an amendment, so every earlier revision is
kept and the register shows which is current. Status and the response stay editable after
issue — an RFI is answered, a drawing approved or superseded, long after it went out.

Adapted from epcforge's Document Register (MIT, Invento Software Limited).
"""

import string

import frappe
from frappe.model.document import Document

PARTIES = ("Supplier", "Customer", "Employee", "Company")


def next_revision(revision):
	"""0 → 1, A → B, Z → AA; anything else gets .1 appended."""
	revision = (revision or "").strip()
	if not revision:
		return "1"
	if revision.isdigit():
		return str(int(revision) + 1)
	if revision.isalpha() and revision.isupper():
		letters = list(revision)
		index = len(letters) - 1
		while index >= 0:
			if letters[index] != "Z":
				letters[index] = string.ascii_uppercase[string.ascii_uppercase.index(letters[index]) + 1]
				return "".join(letters)
			letters[index] = "A"
			index -= 1
		return "A" + "".join(letters)
	return f"{revision}.1"


class FCDocumentRegister(Document):
	def before_insert(self):
		if self.amended_from:
			self.revision = next_revision(frappe.db.get_value("FC Document Register", self.amended_from, "revision"))
			self.status = "Draft"

	def validate(self):
		for kind in ("originator_type", "recipient_type"):
			if self.get(kind) and self.get(kind) not in PARTIES:
				frappe.throw(f"{self.meta.get_label(kind)} must be one of: {', '.join(PARTIES)}.")

	def before_submit(self):
		if self.status == "Draft":
			self.status = "Under Review"

	def on_submit(self):
		# The revision this one replaces is superseded the moment this one is issued.
		if self.amended_from:
			frappe.db.set_value("FC Document Register", self.amended_from, "status", "Superseded",
				update_modified=False)

	def on_cancel(self):
		self.db_set("status", "Cancelled")
