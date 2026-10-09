"""Award → Intacct PROJECT + a TASK per BOQ section, with the BOQ cost as its budget.

Upsert, never duplicate: a project or task Intacct already holds under this key is linked
rather than created again, so a re-run after a part-failure finishes the job instead of
doubling it. The project key is set once, on the BOQ, and never re-keyed.

Lifted from fuse_projects.commercial.award_boq at 0.2.0 (d7eb39c, Syncflo). Phase 2: only
runs with posting switched on in FC Settings.
"""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import frappe
from frappe.utils import now

from fuse_construction.intacct import posting

PROJECT_FIELDS = ["RECORDNO", "PROJECTID", "NAME", "PROJECTSTATUS", "CUSTOMERID"]
TASK_FIELDS = ["RECORDNO", "TASKID", "NAME", "PROJECTID"]

# EPC work is built for a client and billed. IPP plant is the company's own and capitalises.
PROJECT_CATEGORY = {"EPC": "Contract", "IPP": "Capitalized"}


def build_project_xml(boq, project_id, customer_id):
	values = {
		"PROJECTID": project_id,
		"NAME": boq.title,
		"PROJECTCATEGORY": PROJECT_CATEGORY[boq.contract_model],
		"PROJECTSTATUS": "In Progress",
		"CUSTOMERID": customer_id,
		"BEGINDATE": posting.us_date(boq.start_date) if boq.start_date else None,
		"ENDDATE": posting.us_date(boq.end_date) if boq.end_date else None,
		"BUDGETEDCOST": posting.money(boq.total_cost),
		"DESCRIPTION": f"Awarded from Fuse {boq.name}",
	}
	if boq.contract_model == "EPC":
		values["CONTRACTAMOUNT"] = posting.money(boq.contract_value)
		values["BUDGETAMOUNT"] = posting.money(boq.contract_value)
	return posting.create_function("PROJECT", values)


def build_project_update_xml(recordno, boq):
	"""`<update><PROJECT>` — the budget is replaced, never added to."""
	function = ET.Element("function")
	project = ET.SubElement(ET.SubElement(function, "update"), "PROJECT")
	posting.text(project, "RECORDNO", recordno)
	posting.text(project, "BUDGETEDCOST", posting.money(boq.total_cost))
	if boq.contract_model == "EPC":
		posting.text(project, "CONTRACTAMOUNT", posting.money(boq.contract_value))
		posting.text(project, "BUDGETAMOUNT", posting.money(boq.contract_value))
	return function


def build_task_xml(project_id, name, description, task_id=None):
	return posting.create_function(
		"TASK", {"TASKID": task_id, "PROJECTID": project_id, "NAME": name, "DESCRIPTION": description}
	)


def _tasks(project_id):
	tasks = {}
	for row in posting.gateway().query(
		"TASK",
		TASK_FIELDS,
		filter_xml=f"<equalto><field>PROJECTID</field><value>{escape(project_id)}</value></equalto>",
	):
		tasks.setdefault(posting.gateway().val(row, "NAME"), row)
	return tasks


def open_project(boq):
	"""Create or update the job in Intacct. Returns its IDs for the local mirror."""
	gw = posting.gateway()
	customer_id = None
	if boq.contract_model == "EPC":
		customer_id = posting.intacct_id("Customer", boq.customer, "custom_intacct_customer_id", "Clients")

	reference = ("FC BOQ", boq.name)
	project_id = (boq.project_key or "").strip()
	row = posting.find_one("PROJECT", PROJECT_FIELDS, "PROJECTID", project_id) if project_id else None
	if row is None:
		keys = posting.post_first_accepted(
			[
				(posting.stamped(boq, "award_project"), lambda: [build_project_xml(boq, project_id, customer_id)]),
				# Where Intacct numbers projects itself it refuses an ID it did not issue.
				(posting.stamped(boq, "award_project_numbered"), lambda: [build_project_xml(boq, None, customer_id)]),
			],
			reference,
		)
		if keys and keys[0]:
			row = posting.find_one("PROJECT", PROJECT_FIELDS, "RECORDNO", keys[0])
		if row is None and project_id:
			row = posting.find_one("PROJECT", PROJECT_FIELDS, "PROJECTID", project_id)
		if row is None:
			frappe.throw("Intacct accepted the project but it could not be read back. Check Intacct before awarding again.")
	else:
		# Timestamped purpose: an update is idempotent, and a fixed control ID would refuse
		# the second award of a key Intacct already holds.
		gw.execute(build_project_update_xml(gw.val(row, "RECORDNO"), boq), reference=reference,
			purpose=f"award_budget:{now()}")

	project_id = gw.val(row, "PROJECTID")
	sections = list(boq.sections)
	tasks = _tasks(project_id)
	missing = [s for s in sections if s.boq_group not in tasks]
	if missing:
		posting.post_first_accepted(
			[
				(posting.stamped(boq, "award_tasks"),
					lambda: [build_task_xml(project_id, s.boq_group, f"BOQ section {s.boq_group}") for s in missing]),
				(posting.stamped(boq, "award_tasks_numbered"),
					lambda: [build_task_xml(project_id, s.boq_group, f"BOQ section {s.boq_group}",
						f"{project_id}-{s.idx:02d}") for s in missing]),
			],
			reference,
		)
		tasks = _tasks(project_id)
		absent = [s.boq_group for s in sections if s.boq_group not in tasks]
		if absent:
			frappe.throw("Intacct did not return these tasks after creating them: " + ", ".join(absent))

	return {
		"project_id": project_id,
		"recordno": gw.val(row, "RECORDNO"),
		"tasks": {
			s.boq_group: (gw.val(tasks[s.boq_group], "TASKID"), gw.val(tasks[s.boq_group], "RECORDNO"))
			for s in sections
		},
	}
