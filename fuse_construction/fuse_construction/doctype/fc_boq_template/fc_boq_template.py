import frappe
from frappe.model.document import Document
from frappe.utils import flt

from fuse_construction import maths


class FCBOQTemplate(Document):
	def validate(self):
		for row in self.items:
			if row.qty_basis not in maths.QTY_BASIS:
				frappe.throw(f"Row {row.idx}: {row.qty_basis} is not a quantity basis this template understands.")
			if flt(row.qty_factor) < 0 or flt(row.rate) < 0:
				frappe.throw(f"Row {row.idx}: quantity and rate cannot be negative.")
			row.rate = maths.line_rate(row.rate, row.as_dict())

		sections = [row.boq_group for row in self.sections]
		if len(sections) != len(set(sections)):
			frappe.throw("Each section appears once in the programme.")
		billing = sum(flt(row.billing_percent) for row in self.sections)
		if billing > 100.001:
			frappe.throw(f"Billing milestones add up to {billing:g}%. They cannot exceed 100%.")
		lines = {row.boq_group for row in self.items}
		missing = [group for group in sections if group not in lines]
		if missing:
			frappe.msgprint(
				"These programme sections have no lines and will not appear on a BOQ: " + ", ".join(missing),
				indicator="orange",
				alert=True,
			)
