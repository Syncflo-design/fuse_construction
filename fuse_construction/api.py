"""Whitelisted entry points for Fuse Construction."""

import frappe


@frappe.whitelist()
def setup():
	"""Re-apply this app's site configuration — fields, seeds, workflow, workspace, switches.

	Exists because after_migrate does not reliably fire on a Frappe Cloud deploy, and without
	this, repairing that needs bench access.
	"""
	frappe.only_for("System Manager")

	from fuse_construction.install import after_install

	return after_install()
