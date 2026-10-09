"""Construction commercials: template, award, and the documents a BOQ raises.

  * Template — a priced line set that sizes itself to the plant (per kWp / per kWh).
  * Award — a submitted BOQ opens its project with a task per section, and its cost becomes
    the budget. Intacct first when posting is on; Fuse only when it is off.
  * Raise — a quotation for the client, a material request for site, a tender for a
    package, or a subcontract direct.
  * Tender award — the chosen bid becomes a subcontract, or a purchase order for supply.

Award, quotation and material request are adapted from fuse_projects.commercial (Syncflo)
and epcforge's BOQ (MIT, Invento Software Limited) — see THIRD_PARTY_NOTICES.md.
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, now, now_datetime, nowdate

from fuse_construction import costing, maths, settings

# ──────────────────────────────────────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def template_lines(template, capacity_kwp=None, storage_kwh=None):
	"""A template's lines, quantities sized to the plant. Plain dicts, ready to append."""
	doc = frappe.get_cached_doc("FC BOQ Template", template)
	doc.check_permission("read")
	lines = []
	for row in doc.items:
		line = {
			"boq_group": row.boq_group,
			"cost_code": row.cost_code,
			"description": row.description,
			"item_type": row.item_type,
			"phase": row.phase or frappe.db.get_value("FC BOQ Group", row.boq_group, "phase"),
			"cost_head": row.cost_head,
			"item_code": row.item_code,
			"preferred_supplier": row.preferred_supplier,
			"qty_basis": row.qty_basis,
			"qty_factor": row.qty_factor,
			"qty": maths.template_qty(row.qty_basis or "Fixed", row.qty_factor, capacity_kwp, storage_kwh),
			"uom": row.uom,
			"rate": row.rate,
		}
		for field in maths.BUILD_UP:
			line[field] = row.get(field)
		lines.append(line)
	return lines


def template_plan(template):
	"""{section: (start_week, duration_weeks, billing_percent)} from a template."""
	if not template:
		return {}
	return {
		row.boq_group: (cint(row.start_week), cint(row.duration_weeks), flt(row.billing_percent))
		for row in frappe.get_cached_doc("FC BOQ Template", template).sections
	}


# ──────────────────────────────────────────────────────────────────────────────
# Award
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def award_boq(boq):
	"""Open the job: a project, a task per section, and the budget.

	Awarding is a commercial decision, so it takes the same right as submitting the BOQ. With
	Intacct posting on, the project and its tasks are opened in Intacct FIRST and mirrored
	here; a rejection stops the award with nothing created locally.
	"""
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("submit")
	return award(doc)


def award(doc, ignore_permissions=False):
	"""The award itself. `ignore_permissions` is for automation that has already decided —
	a CRM deal marked Won — never for a user's click."""
	if doc.docstatus != 1:
		frappe.throw("Submit the BOQ first. Its price is what the budget is set from.")
	if doc.status == "Awarded":
		frappe.throw(f"{doc.name} is already awarded, to {doc.project}.")
	if not doc.sections:
		frappe.throw("This BOQ has no priced sections to open as tasks.")

	intacct = None
	if settings.intacct_posting_on():
		from fuse_construction.intacct import award as intacct_award

		intacct = intacct_award.open_project(doc)

	project = _project_for(doc, intacct, ignore_permissions)
	company = frappe.db.get_value("Project", project, "company")
	project_end = frappe.db.get_value("Project", project, "expected_end_date")

	tasks = {}
	for row in doc.sections:
		task_ids = (intacct or {}).get("tasks", {}).get(row.boq_group)
		row.task = _task_for(project, company, project_end, doc, row, task_ids, ignore_permissions)
		tasks[row.boq_group] = row.task
		if task_ids:
			row.intacct_task_id, row.intacct_task_recordno = task_ids

	for item in doc.items:
		item.task = tasks.get(item.boq_group)
	for milestone in doc.milestones:
		milestone.task = tasks.get(milestone.boq_group)

	doc.project = project
	doc.status = "Awarded"
	doc.awarded_on = now()
	if intacct:
		doc.intacct_project_id = intacct["project_id"]
		doc.intacct_project_recordno = intacct["recordno"]
	doc.flags.awarding = True
	doc.save(ignore_permissions=ignore_permissions)

	frappe.db.set_value("Project", project, "fc_boq", doc.name, update_modified=False)
	budget = costing.ensure_budget(doc)
	return {"project": project, "tasks": len(tasks), "budget": budget}


def _project_for(doc, intacct, ignore_permissions=False):
	"""The project to award into: the one chosen, one Intacct already knows, or a new one."""
	if doc.project:
		return doc.project

	# A project Intacct already holds under this code — brought across by the fuse_projects
	# sync, typically. Awarding into it keeps one project per job instead of two.
	key = (intacct or {}).get("project_id") or doc.project_key
	if key and _has_field("Project", "custom_intacct_project_id"):
		existing = frappe.db.get_value("Project", {"custom_intacct_project_id": key}, "name")
		if existing:
			other = frappe.db.get_value(
				"FC BOQ", {"project": existing, "docstatus": 1, "name": ["!=", doc.name]}, "name"
			)
			if other:
				frappe.throw(f"Project {existing} (Intacct {key}) is already run by {other}.")
			return existing

	starts = [getdate(d) for d in [doc.start_date] + [r.planned_start for r in doc.sections] if d]
	ends = [getdate(d) for d in [doc.end_date] + [r.planned_end for r in doc.sections] if d]

	project = frappe.new_doc("Project")
	project.project_name = _unique_project_name(doc.title, doc.project_key)
	project.company = doc.company
	if doc.contract_model == "EPC":
		project.customer = doc.customer
	project.expected_start_date = min(starts) if starts else None
	# Never earlier than the last section's finish: ERPNext refuses a task that ends after
	# its project, and the baseline is the BOQ's, not the project header's.
	project.expected_end_date = max(ends) if ends else None
	project.estimated_costing = doc.total_cost
	project.status = "Open"
	if intacct and _has_field("Project", "custom_intacct_project_id"):
		project.custom_intacct_project_id = intacct["project_id"]
		project.custom_intacct_recordno = intacct["recordno"]
		# It exists in Intacct as of a moment ago — the one door fuse_projects' project lock
		# lets through, and the right one.
		project.flags.from_intacct_sync = True
	project.insert(ignore_permissions=ignore_permissions)
	return project.name


def _unique_project_name(title, key):
	"""The BOQ's name for the project, made unique with its code when another job has it."""
	name = (title or key or "Project").strip()
	candidate = name
	counter = 1
	while frappe.db.exists("Project", {"project_name": candidate}):
		suffix = key if counter == 1 and key else f"{key or ''} {counter}".strip()
		candidate = f"{name} ({suffix})"
		counter += 1
	return candidate


def _task_for(project, company, project_end, boq, section, task_ids, ignore_permissions=False):
	"""The section's task on the project — an existing one if it is already there."""
	existing = None
	if task_ids and _has_field("Task", "custom_intacct_task_id"):
		existing = frappe.db.get_value(
			"Task", {"project": project, "custom_intacct_task_id": task_ids[0]}, "name"
		)
	existing = (
		existing
		or frappe.db.get_value("Task", {"project": project, "fc_boq_group": section.boq_group}, "name")
		or frappe.db.get_value("Task", {"project": project, "subject": section.boq_group}, "name")
	)

	task = frappe.get_doc("Task", existing) if existing else frappe.new_doc("Task")
	task.fc_boq = boq.name
	task.fc_boq_group = section.boq_group
	if not existing:
		task.subject = section.boq_group
		task.project = project
		task.company = company
		task.description = f"BOQ section, budget {frappe.format_value(section.cost, {'fieldtype': 'Currency'})}"
		task.exp_start_date = _clamp(section.planned_start, project_end)
		task.exp_end_date = _clamp(section.planned_end, project_end)
	if task_ids and _has_field("Task", "custom_intacct_task_id"):
		task.custom_intacct_task_id, task.custom_intacct_recordno = task_ids
		task.custom_intacct_project_id = boq.intacct_project_id or boq.project_key
		# Already in Intacct — stops fuse_projects creating it there a second time.
		task.flags.from_intacct_sync = True
	task.save(ignore_permissions=ignore_permissions)
	return task.name


def _clamp(day, project_end):
	if not day:
		return None
	if project_end and getdate(day) > getdate(project_end):
		return getdate(project_end)
	return getdate(day)


def _has_field(doctype, fieldname):
	return frappe.get_meta(doctype).has_field(fieldname)


# ──────────────────────────────────────────────────────────────────────────────
# Documents a BOQ raises
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def make_quotation(boq, by="Section"):
	"""A draft ERPNext Quotation for the client, by section or as one lump sum.

	For the client's eyes only: it does not post to Intacct and it does not become the
	billing. Valuations and milestones do that.
	"""
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("read")
	if doc.contract_model != "EPC" or not doc.customer:
		frappe.throw("A quotation goes to a client. This is not an EPC job with a client.")
	item_code = settings.get("quotation_item")
	if not item_code:
		frappe.throw("Choose the Quotation Item in FC Settings — the non-stock sales item a quotation is priced on.")

	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = doc.customer
	quotation.company = doc.company
	quotation.transaction_date = nowdate()
	quotation.valid_till = add_days(nowdate(), 30)
	quotation.fc_boq = doc.name
	uom = frappe.db.get_value("Item", item_code, "stock_uom")

	if by == "Lump Sum":
		lines = [(doc.title, f"{doc.title}: supply, installation and commissioning", doc.contract_value)]
	else:
		lines = [
			(row.boq_group, f"{row.boq_group} — {doc.title}", row.contract_value)
			for row in doc.sections
		]
	for name, description, value in lines:
		quotation.append(
			"items",
			{
				"item_code": item_code,
				"item_name": name[:140],
				"description": description,
				"qty": 1,
				"uom": uom,
				"rate": value,
			},
		)
	quotation.insert()
	doc.db_set("quotation", quotation.name)
	return quotation.name


@frappe.whitelist()
def make_material_request(boq, boq_group=None):
	"""A draft Material Request for the BOQ's material lines that are purchasable items."""
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("read")
	if doc.status != "Awarded":
		frappe.throw("Award the BOQ first. A material request is raised against its project.")
	warehouse = settings.get("site_warehouse") or frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if not warehouse:
		frappe.throw("Set the Site Warehouse in FC Settings — material requests are raised for it.")

	request = frappe.new_doc("Material Request")
	request.material_request_type = "Purchase"
	request.company = doc.company
	request.transaction_date = nowdate()
	request.schedule_date = add_days(nowdate(), 7)
	request.set_warehouse = warehouse
	for row in doc.items:
		if row.item_type != "Material" or not row.item_code or flt(row.qty) <= 0:
			continue
		if boq_group and row.boq_group != boq_group:
			continue
		if not frappe.db.get_value("Item", row.item_code, "is_purchase_item"):
			continue
		request.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"uom": frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"schedule_date": request.schedule_date,
				"warehouse": warehouse,
				"project": doc.project,
				"fc_task": row.task,
				"description": row.description,
			},
		)
	if not request.items:
		frappe.throw("No material lines with a purchasable item to request.")
	request.insert()
	return request.name


@frappe.whitelist()
def make_tender(boq, boq_group, package_type="Subcontract"):
	"""A draft tender for one section, its scope and estimate taken from the BOQ."""
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("read")
	wanted = {"Subcontract": ("Subcontract",), "Supply": ("Material",)}.get(package_type, ())
	lines = [r for r in doc.items if r.boq_group == boq_group and r.item_type in wanted]
	# A section priced by trade rather than as one package still goes out whole.
	if not lines:
		lines = [r for r in doc.items if r.boq_group == boq_group]
	if not lines:
		frappe.throw(f"{boq_group} has no lines on {doc.name}.")

	tender = frappe.new_doc("FC Tender")
	tender.tender_title = f"{boq_group} — {doc.title}"
	tender.project = doc.project
	tender.boq = doc.name
	tender.boq_group = boq_group
	tender.package_type = package_type
	tender.company = doc.company
	tender.tender_type = "Limited Tender"
	tender.publish_date = nowdate()
	tender.submission_deadline = frappe.utils.add_to_date(now_datetime(), days=14)
	for row in lines:
		tender.append(
			"items",
			{
				"boq_item": row.name,
				"boq_group": row.boq_group,
				"cost_code": row.cost_code,
				"description": row.description,
				"item_code": row.item_code,
				"qty": row.qty,
				"uom": row.uom,
				"estimated_rate": row.rate,
			},
		)
	tender.scope_of_work = "<ul>" + "".join(
		f"<li>{frappe.utils.escape_html(r.cost_code or '')} {frappe.utils.escape_html(r.description)}: "
		f"{flt(r.qty):g} {frappe.utils.escape_html(r.uom or '')}</li>"
		for r in lines
	) + "</ul>"
	tender.insert()
	return tender.name


@frappe.whitelist()
def make_subcontract(boq, boq_group, supplier=None):
	"""A draft subcontract for one section, direct — no tender."""
	doc = frappe.get_doc("FC BOQ", boq)
	doc.check_permission("read")
	if doc.status != "Awarded":
		frappe.throw("Award the BOQ first. A subcontract is let against its project.")
	lines = [r for r in doc.items if r.boq_group == boq_group and r.item_type == "Subcontract"] or [
		r for r in doc.items if r.boq_group == boq_group
	]
	sub = _new_subcontract(doc, boq_group, supplier)
	for row in lines:
		sub.append(
			"lines",
			{
				"boq_item": row.name,
				"boq_group": row.boq_group,
				"description": row.description,
				"qty": row.qty or 1,
				"uom": row.uom,
				"rate": row.rate,
			},
		)
	sub.insert()
	return sub.name


def _new_subcontract(boq, boq_group, supplier):
	sub = frappe.new_doc("FC Subcontract")
	sub.title = f"{boq_group} — {boq.title}" if boq_group else boq.title
	sub.supplier = supplier
	sub.project = boq.project
	sub.boq = boq.name
	sub.company = boq.company
	section = next((r for r in boq.sections if r.boq_group == boq_group), None)
	sub.start_date = (section and section.planned_start) or boq.start_date or nowdate()
	sub.end_date = (section and section.planned_end) or boq.end_date
	return sub


# ──────────────────────────────────────────────────────────────────────────────
# Tender award
# ──────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def set_tender_status(tender, status):
	doc = frappe.get_doc("FC Tender", tender)
	doc.check_permission("write")
	if doc.docstatus != 1:
		frappe.throw("Publish (submit) the tender first.")
	if status not in ("Published", "Under Evaluation"):
		frappe.throw(f"{status} is set by awarding or cancelling, not directly.")
	if doc.status in ("Awarded", "Cancelled"):
		frappe.throw(f"{doc.name} is {doc.status.lower()}.")
	doc.status = status
	doc.save()
	return doc.status


@frappe.whitelist()
def award_tender(tender, supplier):
	"""Award to one bidder: a subcontract (draft) or a purchase order (draft) at their price.

	Drafts, deliberately. The award decides who; the document still has to be checked and
	submitted by someone who will stand behind its terms.
	"""
	doc = frappe.get_doc("FC Tender", tender)
	doc.check_permission("submit")
	if doc.docstatus != 1:
		frappe.throw("Publish (submit) the tender before awarding it.")
	if doc.status in ("Awarded", "Cancelled"):
		frappe.throw(f"{doc.name} is already {doc.status.lower()}.")

	bidder = next((row for row in doc.bidders if row.supplier == supplier), None)
	if not bidder:
		frappe.throw(f"{supplier} did not bid on {doc.name}.")
	if flt(bidder.bid_amount) <= 0 or bidder.bid_status == "Declined":
		frappe.throw(f"{supplier} has no bid to award.")

	for row in doc.bidders:
		if row is bidder:
			row.bid_status = "Awarded"
		elif row.bid_status != "Declined":
			row.bid_status = "Not Awarded"
	doc.awarded_to = supplier
	doc.award_amount = bidder.bid_amount
	doc.award_date = nowdate()
	doc.status = "Awarded"

	if doc.package_type == "Supply":
		doc.purchase_order = _order_from_tender(doc, bidder)
		result = {"doctype": "Purchase Order", "name": doc.purchase_order}
	else:
		doc.subcontract = _subcontract_from_tender(doc, bidder)
		result = {"doctype": "FC Subcontract", "name": doc.subcontract}
	doc.save()
	return result


def _scaled_lines(tender, award):
	"""Tender lines repriced so they add up to the award.

	A bid is usually one number; the scope is many lines. Scaling every estimated rate by
	the same factor keeps each section's share of the work as estimated, which is what the
	cost report needs to put certified work in the right place.
	"""
	estimate = sum(flt(row.qty) * flt(row.estimated_rate) for row in tender.items)
	if not tender.items or estimate <= 0:
		return None
	factor = flt(award) / estimate
	lines = []
	for row in tender.items:
		lines.append(
			{
				"boq_item": row.boq_item,
				"boq_group": row.boq_group or tender.boq_group,
				"description": row.description,
				"item_code": row.item_code,
				"qty": flt(row.qty) or 1,
				"uom": row.uom,
				"rate": maths.money(flt(row.estimated_rate) * factor),
			}
		)
	# The last line takes the rounding, so the lines meet the award to the cent where its
	# quantity allows.
	others = sum(maths.money(line["qty"] * line["rate"]) for line in lines[:-1])
	lines[-1]["rate"] = maths.money((flt(award) - others) / lines[-1]["qty"])
	return lines


def _subcontract_from_tender(tender, bidder):
	boq = frappe.get_doc("FC BOQ", tender.boq) if tender.boq else None
	if boq and boq.status != "Awarded":
		frappe.throw(f"Award {boq.name} first — the subcontract is let against its project.")
	if not tender.project and not boq:
		frappe.throw("The tender has no project to let the subcontract against.")

	if boq:
		sub = _new_subcontract(boq, tender.boq_group, bidder.supplier)
	else:
		sub = frappe.new_doc("FC Subcontract")
		sub.title = tender.tender_title
		sub.supplier = bidder.supplier
		sub.project = tender.project
		sub.company = tender.company
		sub.start_date = nowdate()
	sub.tender = tender.name
	if bidder.programme_weeks and sub.start_date:
		sub.end_date = add_days(sub.start_date, cint(bidder.programme_weeks) * 7)

	lines = _scaled_lines(tender, bidder.bid_amount)
	if lines is None:
		if not tender.boq_group:
			frappe.throw("Give the tender a section, or scope lines, so the subcontract knows where its cost belongs.")
		lines = [{"boq_group": tender.boq_group, "description": tender.tender_title, "qty": 1,
			"rate": bidder.bid_amount}]
	for line in lines:
		line.pop("item_code", None)
		sub.append("lines", line)
	sub.insert()
	return sub.name


def _order_from_tender(tender, bidder):
	lines = _scaled_lines(tender, bidder.bid_amount)
	if not lines or any(not line["item_code"] for line in lines):
		frappe.throw("A supply award becomes a purchase order, and every line needs an item for that.")
	boq = frappe.get_doc("FC BOQ", tender.boq) if tender.boq else None
	tasks = {row.boq_group: row.task for row in boq.sections} if boq else {}

	order = frappe.new_doc("Purchase Order")
	order.supplier = bidder.supplier
	order.company = tender.company
	order.transaction_date = nowdate()
	order.schedule_date = add_days(nowdate(), 14)
	if order.meta.has_field("project"):
		order.project = tender.project
	order.fc_boq = tender.boq
	for line in lines:
		order.append(
			"items",
			{
				"item_code": line["item_code"],
				"description": line["description"],
				"qty": line["qty"],
				# The item's own unit. A BOQ's "No" against an item stocked in "Nos" would need a
				# conversion factor nobody set, and the order would refuse to save.
				"uom": frappe.db.get_value("Item", line["item_code"], "stock_uom"),
				"rate": line["rate"],
				"schedule_date": order.schedule_date,
				"project": tender.project,
				"fc_task": tasks.get(line["boq_group"]),
			},
		)
	order.insert()
	return order.name
