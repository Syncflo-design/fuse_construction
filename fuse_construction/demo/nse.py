"""The NSE Energy demo profile: a C&I solar PV + battery job, awarded and ready to run.

Demo setup, not product. Run on the Fuse demo site from the FC BOQ list (menu: Load Construction
Demo) after the outgoing profile has been backed up (demo_profiles/PROFILES.md). Idempotent:
a second run finds what the first made and adds only what is missing.

Every name is fictitious — never NSE's real clients. Nothing is read from or written to
Intacct.

What it makes:
  * the template "C&I Solar PV + BESS": ten sections with a programme and billing milestones,
    lines that scale per kWp / MWp / kWh / MWh;
  * the job "Breede River Packhouse 6.5 MWp PV + 7 MWh BESS", starting next Monday, priced
    from the template, submitted and awarded — a project with a task per section, and its budget;
  * an EPC client, two subcontractors, three suppliers and two more civils bidders;
  * nine workers with trades and rates, for crew time on the phone;
  * the civils tender, published with three bids in — the award is the demo;
  * demo commercial terms: subcontract advance 10% recovered at 20%, retention 5% capped at
    5%, released 50% at practical completion and 50% after a 12-month DLP;
  * three CRM leads and one deal at proposal, where Frappe CRM is installed;
  * all of it in its own company, "Construction", beside the manufacturing one. A presenter
    login limited to that company (User Permission) and given a construction role and module
    profile sees only this job; nothing site-wide is switched off.

Nothing is certified, valued, booked or received. Those are the demo.
"""

import frappe
from frappe.utils import add_days, add_years, getdate, now_datetime, nowdate

from fuse_construction import commercial

TEMPLATE = "C&I Solar PV + BESS"
TITLE = "Breede River Packhouse 6.5 MWp PV + 7 MWh BESS"

# The demo site carries one company per profile. This one is the contractor.
COMPANY = "Construction"
COMPANY_ABBR = "CON"

# Its items, suppliers and client sit in item / supplier / customer groups of this name, so a
# presenter limited to them sees none of the manufacturing profile's masters.
GROUP = "Construction"
CLIENT = "Breede River Packhouse (Pty) Ltd"

SUBCONTRACTORS = {
	"civils": "Klein Karoo Civils (Pty) Ltd",
	"electrical": "Boland Electrical Contractors (Pty) Ltd",
}
SUPPLIERS = {
	"modules": "Helios Solar Supply (Pty) Ltd",
	"inverters": "Cape Power Electronics (Pty) Ltd",
	"batteries": "Southern Storage Systems (Pty) Ltd",
}
CIVILS_BIDDERS = [
	# (supplier, bid as a share of the estimate, programme weeks, compliant)
	(SUBCONTRACTORS["civils"], 0.97, 8, 1),
	("Swartland Earthworks (Pty) Ltd", 1.04, 7, 1),
	("Overberg Plant and Civils (Pty) Ltd", 0.91, 10, 0),
]

ITEMS = [
	# (code, name, stock unit, purchased, sold) — all non-stock: the demo moves no stock.
	("CON-PV-550", "PV module 550 Wp, bifacial", "No", 1, 0),
	("CON-INV-100", "String inverter 100 kW", "No", 1, 0),
	("CON-BESS", "Battery energy storage, containerised (per kWh)", "kWh", 1, 0),
	("FC-SUBCONTRACT", "Subcontract works", "LS", 1, 0),
	("FC-EPC-WORKS", "EPC works", "LS", 0, 1),
]

UOMS = ["No", "LS", "ha", "m", "m3", "km", "kWp", "kWh", "MWp", "MWh", "Month"]

# (section, start week, duration weeks, billing %)
SECTIONS = [
	("Preliminaries and General", 0, 26, 5),
	("Engineering and Design", 0, 6, 5),
	("Civils and Earthworks", 2, 8, 15),
	("Mounting Structures", 6, 8, 15),
	("PV Modules", 4, 12, 20),
	("Inverters", 8, 8, 10),
	("Battery Storage (BESS)", 10, 10, 15),
	("DC and AC Cabling", 10, 10, 8),
	("MV Grid Connection", 14, 8, 5),
	("Commissioning", 22, 4, 2),
]

# (section, cost code, description, basis, factor, uom, rate, type, item, build-up)
LINES = [
	("Preliminaries and General", "PG-010", "Site establishment and de-establishment", "Fixed", 1, "LS", 450000, "Overhead", None, None),
	("Preliminaries and General", "PG-020", "Site management and supervision", "Fixed", 6, "Month", 185000, "Labour", None, None),
	("Preliminaries and General", "PG-030", "Health, safety and environmental compliance", "Fixed", 1, "LS", 220000, "Overhead", None, None),
	("Engineering and Design", "ENG-010", "Detailed design and geotechnical survey", "Per MWp", 1, "MWp", 95000, "Subcontract", None, None),
	("Engineering and Design", "ENG-020", "Grid connection application and studies", "Fixed", 1, "LS", 380000, "Subcontract", None, None),
	("Civils and Earthworks", "CIV-010", "Site clearance and grubbing", "Per MWp", 1.8, "ha", 43000, "Subcontract", None, None),
	("Civils and Earthworks", "CIV-020", "Bulk earthworks, cut and fill", "Per MWp", 2800, "m3", 115, "Subcontract", None, None),
	("Civils and Earthworks", "CIV-030", "Internal gravel access roads", "Per MWp", 480, "m", 680, "Subcontract", None, None),
	("Civils and Earthworks", "CIV-040", "Perimeter security fence, 2.4 m clear-view", "Per MWp", 245, "m", 0, "Subcontract", None,
		{"labour_rate": 210, "plant_rate": 70, "material_rate": 400, "subcontract_rate": 80}),
	("Civils and Earthworks", "CIV-050", "BESS and transformer plinths", "Per MWh", 1, "No", 185000, "Subcontract", None, None),
	("Mounting Structures", "MNT-010", "Driven steel piles", "Per kWp", 0.74, "No", 680, "Subcontract", None, None),
	("Mounting Structures", "MNT-020", "Fixed-tilt structures, supply and erect", "Per kWp", 1, "kWp", 1120, "Subcontract", None, None),
	("PV Modules", "PVM-010", "PV modules 550 Wp bifacial, supply", "Per kWp", 1.818, "No", 2070, "Material", "CON-PV-550", None),
	("PV Modules", "PVM-020", "Module installation", "Per kWp", 1.818, "No", 110, "Labour", None, None),
	("Inverters", "INV-010", "String inverters 100 kW, supply", "Per MWp", 7.6923, "No", 93600, "Material", "CON-INV-100", None),
	("Inverters", "INV-020", "Inverter installation and commissioning", "Per MWp", 7.6923, "No", 11700, "Labour", None, None),
	("Battery Storage (BESS)", "BES-010", "Battery energy storage system, containerised, supply", "Per kWh", 1, "kWh", 4200, "Material", "CON-BESS", None),
	("Battery Storage (BESS)", "BES-020", "BESS installation, integration and EMS", "Per MWh", 1, "MWh", 210000, "Subcontract", None, None),
	("DC and AC Cabling", "CAB-010", "DC string cabling", "Per kWp", 7.4, "m", 34, "Subcontract", None, None),
	("DC and AC Cabling", "CAB-020", "AC LV cabling including trenching", "Per MWp", 1000, "m", 430, "Subcontract", None, None),
	("MV Grid Connection", "MV-010", "MV switchgear and transformer stations", "Fixed", 2, "No", 3330000, "Subcontract", None, None),
	("MV Grid Connection", "MV-020", "MV overhead line to point of connection", "Fixed", 2.5, "km", 1730000, "Subcontract", None, None),
	("Commissioning", "COM-010", "Testing, commissioning and performance test", "Per MWp", 1, "MWp", 65000, "Subcontract", None, None),
	("Commissioning", "COM-020", "Handover documentation and training", "Fixed", 1, "LS", 120000, "Overhead", None, None),
]

# (activity type, costing rate per hour)
TRADES = [("General Labour", 65), ("Installer", 95), ("Electrician", 145), ("Plant Operator", 120), ("Foreman", 180)]

# (first, last, gender, trade, worker type)
WORKERS = [
	("Sipho", "Mthembu", "Male", "Foreman", "Employee"),
	("Thandeka", "Nkosi", "Female", "Electrician", "Employee"),
	("Johan", "van Wyk", "Male", "Electrician", "Employee"),
	("Lerato", "Mokoena", "Female", "Installer", "Employee"),
	("Pieter", "Botha", "Male", "Installer", "Employee"),
	("Ayanda", "Dlamini", "Female", "Installer", "Labour Broker"),
	("Bongani", "Zulu", "Male", "General Labour", "Labour Broker"),
	("Riaan", "Pretorius", "Male", "Plant Operator", "Employee"),
	("Nomsa", "Khumalo", "Female", "General Labour", "Labour Broker"),
]
LABOUR_BROKER = "Winelands Labour Solutions (Pty) Ltd"


def is_demo_site():
	"""Only a site whose config sets `fuse_demo_site` is a demo site. A client's never is.

	This loader makes a company, groups, suppliers and a job. On a client's live site that is
	not a demo, it is pollution — so the guard is in the site's config, which belongs to the
	site and is not carried by a backup or an app update.
	"""
	return bool(frappe.conf.get("fuse_demo_site"))


def boot(bootinfo):
	bootinfo.fuse_demo_site = is_demo_site()


@frappe.whitelist()
def load(project_key="CON-DEMO-6M5"):
	frappe.only_for("System Manager")
	if not is_demo_site():
		frappe.throw(
			"The construction demo loads only on the Fuse demo site — set fuse_demo_site in that "
			"site's config. It never loads on a client's site."
		)
	project_key = (project_key or "CON-DEMO-6M5").strip()

	from fuse_construction.install import after_install

	after_install()
	company = _company()
	for uom in UOMS:
		_ensure_uom(uom)
	for code, name, uom, purchase, sales in ITEMS:
		_ensure_item(code, name, uom, purchase, sales)
	parties = {}
	for name in list(SUBCONTRACTORS.values()) + list(SUPPLIERS.values()) + [b[0] for b in CIVILS_BIDDERS] + [LABOUR_BROKER]:
		parties[name] = _ensure_party("Supplier", name)
	client = _ensure_party("Customer", CLIENT)
	_trades()
	# After the trades: the settings name one as the default activity type.
	_settings(company)
	workers = _workers(company, parties[LABOUR_BROKER])
	_sections()
	_template()
	boq = _boq(project_key, company, client)
	tender = _civils_tender(boq)
	crm = _crm()
	frappe.db.commit()

	doc = frappe.get_doc("FC BOQ", boq)
	summary = (
		f"BOQ <b>{doc.name}</b> ({doc.title}) awarded as project <b>{doc.project}</b>: "
		f"{len(doc.sections)} sections, budget {frappe.format_value(doc.total_cost, {'fieldtype': 'Currency'})}, "
		f"contract {frappe.format_value(doc.contract_value, {'fieldtype': 'Currency'})}.<br>"
		f"Civils tender <b>{tender}</b> published with three bids — award it to start the story.<br>"
		f"{len(workers)} workers with trades and rates. Client: {CLIENT}.<br>"
		f"CRM: {crm}. Company: {company}."
	)
	return {"boq": boq, "project": doc.project, "tender": tender, "summary": summary}


def _company():
	"""The profile's own company, created the first time with ERPNext's standard chart.

	Its own rather than the site's existing one, so the manufacturing profile and this one
	share the site without sharing a project list, a warehouse or a budget.
	"""
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"country": "South Africa",
				"default_currency": "ZAR",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		).insert(ignore_permissions=True)
	return COMPANY


def _site_warehouse(company):
	"""A store in this company for site deliveries — ERPNext makes "Stores" with the company."""
	return frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0, "warehouse_name": "Stores"}, "name"
	) or frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")


def _ensure_uom(name):
	if not frappe.db.exists("UOM", name):
		frappe.get_doc({"doctype": "UOM", "uom_name": name, "must_be_whole_number": 0}).insert(ignore_permissions=True)


def _group(doctype):
	"""This profile's own group in an item / supplier / customer group tree, made if missing."""
	field = frappe.scrub(doctype)  # item_group, supplier_group, customer_group
	if not frappe.db.exists(doctype, GROUP):
		root = frappe.db.get_value(doctype, {"is_group": 1, f"parent_{field}": ("is", "not set")}, "name")
		frappe.get_doc(
			{"doctype": doctype, f"{field}_name": GROUP, f"parent_{field}": root, "is_group": 0}
		).insert(ignore_permissions=True)
	return GROUP


def _leaf(doctype, preferred):
	if preferred and frappe.db.exists(doctype, preferred):
		return preferred
	return frappe.get_all(doctype, filters={"is_group": 0}, pluck="name", limit=1)[0]


def _ensure_item(code, name, uom, purchase, sales):
	if frappe.db.exists("Item", code):
		frappe.db.set_value("Item", code, "item_group", _group("Item Group"))
		return code
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": name,
			"description": name,
			"item_group": _group("Item Group"),
			"stock_uom": uom,
			"is_stock_item": 0,
			"is_purchase_item": purchase,
			"is_sales_item": sales,
			"include_item_in_manufacturing": 0,
		}
	).insert(ignore_permissions=True)
	return code


def _ensure_party(doctype, name):
	field = "supplier_name" if doctype == "Supplier" else "customer_name"
	group_doctype = f"{doctype} Group"
	existing = frappe.db.get_value(doctype, {field: name}, "name")
	if existing:
		frappe.db.set_value(doctype, existing, frappe.scrub(group_doctype), _group(group_doctype))
		return existing
	doc = frappe.new_doc(doctype)
	doc.set(field, name)
	if doctype == "Supplier":
		doc.supplier_group = _group(group_doctype)
	else:
		doc.customer_group = _group(group_doctype)
		doc.territory = _leaf("Territory", "South Africa")
		doc.customer_type = "Company"
	doc.insert(ignore_permissions=True)
	return doc.name


def _settings(company):
	settings = frappe.get_single("FC Settings")
	settings.default_company = company
	# A store in another company would be refused on every delivery booked for this job.
	current = settings.site_warehouse
	if not current or frappe.db.get_value("Warehouse", current, "company") != company:
		settings.site_warehouse = _site_warehouse(company)
	settings.default_activity_type = settings.default_activity_type or "General Labour"
	settings.subcontract_item = settings.subcontract_item or "FC-SUBCONTRACT"
	settings.quotation_item = settings.quotation_item or "FC-EPC-WORKS"
	# The demo's commercial terms (plan §8). NSE's real terms are still to be confirmed.
	settings.sub_retention_percent = 5
	settings.sub_retention_cap_percent = 5
	settings.sub_advance_percent = 10
	settings.sub_advance_recovery_percent = 20
	settings.client_retention_percent = 5
	settings.client_retention_cap_percent = 5
	settings.dlp_months = 12
	settings.standard_day_hours = 8
	settings.auto_overtime = 1
	settings.post_to_intacct = 0
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache("FC Settings", "FC Settings")


def _trades():
	for name, rate in TRADES:
		if frappe.db.exists("Activity Type", name):
			frappe.db.set_value("Activity Type", name, "costing_rate", rate)
		else:
			frappe.get_doc({"doctype": "Activity Type", "activity_type": name, "costing_rate": rate}).insert(
				ignore_permissions=True
			)


def _workers(company, broker):
	names = []
	gender_default = frappe.get_all("Gender", pluck="name", limit=1)
	for first, last, gender, trade, kind in WORKERS:
		full = f"{first} {last}"
		existing = frappe.db.get_value("Employee", {"employee_name": full, "company": company}, "name")
		if existing:
			names.append(existing)
			continue
		doc = frappe.new_doc("Employee")
		doc.first_name = first
		doc.last_name = last
		doc.gender = gender if frappe.db.exists("Gender", gender) else (gender_default[0] if gender_default else None)
		doc.date_of_birth = add_years(getdate(nowdate()), -30)
		doc.date_of_joining = add_years(getdate(nowdate()), -2)
		doc.company = company
		doc.status = "Active"
		doc.fc_trade = trade
		doc.fc_worker_type = kind
		if kind == "Labour Broker":
			doc.fc_labour_broker = broker
		doc.insert(ignore_permissions=True)
		names.append(doc.name)
		# The foreman is costed at his own rate, the rest at their trade's — both ways the
		# rate is found, shown in one crew.
		if trade == "Foreman" and not frappe.db.exists("Activity Cost", {"employee": doc.name, "activity_type": "Foreman"}):
			frappe.get_doc({"doctype": "Activity Cost", "employee": doc.name, "activity_type": "Foreman",
				"costing_rate": 195}).insert(ignore_permissions=True)
	return names


def _sections():
	"""The template's sections, on a site whose own list does not have them."""
	from fuse_construction.install import BOQ_GROUPS

	phases = {name: (phase, prefix) for name, phase, prefix in BOQ_GROUPS}
	for section, _week, _duration, _billing in SECTIONS:
		if not frappe.db.exists("FC BOQ Group", section):
			phase, prefix = phases.get(section, ("Construction", None))
			frappe.get_doc({"doctype": "FC BOQ Group", "boq_group_name": section, "is_group": 0, "phase": phase,
				"cost_code_prefix": prefix}).insert(ignore_permissions=True)


def _template():
	if frappe.db.exists("FC BOQ Template", TEMPLATE):
		return TEMPLATE
	template = frappe.new_doc("FC BOQ Template")
	template.template_name = TEMPLATE
	template.contract_model = "EPC"
	template.markup_percent = 15
	template.description = "Commercial and industrial rooftop/ground-mount PV with containerised battery storage."
	for section, week, duration, billing in SECTIONS:
		template.append("sections", {"boq_group": section, "start_week": week, "duration_weeks": duration,
			"billing_percent": billing})
	for section, code, description, basis, factor, uom, rate, kind, item, build_up in LINES:
		row = {"boq_group": section, "cost_code": code, "description": description, "qty_basis": basis,
			"qty_factor": factor, "uom": uom, "rate": rate, "item_type": kind, "item_code": item}
		row.update(build_up or {})
		template.append("items", row)
	template.insert(ignore_permissions=True)
	return template.name


def _boq(project_key, company, client):
	existing = frappe.db.get_value("FC BOQ", {"project_key": project_key, "docstatus": ["<", 2]}, "name")
	if existing:
		doc = frappe.get_doc("FC BOQ", existing)
	else:
		doc = frappe.new_doc("FC BOQ")
		doc.title = TITLE
		doc.project_key = project_key
		doc.contract_model = "EPC"
		doc.contract_type = "Lump Sum"
		doc.customer = client
		doc.company = company
		doc.template = TEMPLATE
		doc.capacity_kwp = 6500
		doc.storage_kwh = 7000
		# Next Monday: a job starting today is already behind its own programme by tonight.
		today = getdate(nowdate())
		doc.start_date = add_days(today, 7 - today.weekday())
		doc.billing_basis = "Milestones"
		doc.insert(ignore_permissions=True)
	if doc.docstatus == 0:
		doc.submit()
	if doc.status != "Awarded":
		commercial.award(doc, ignore_permissions=True)
	return doc.name


def _civils_tender(boq_name):
	existing = frappe.db.get_value("FC Tender", {"boq": boq_name, "boq_group": "Civils and Earthworks", "docstatus": ["<", 2]},
		"name")
	if existing:
		return existing
	name = commercial.make_tender(boq_name, "Civils and Earthworks", "Subcontract")
	tender = frappe.get_doc("FC Tender", name)
	estimate = tender.estimated_value
	for supplier, share, weeks, compliant in CIVILS_BIDDERS:
		tender.append(
			"bidders",
			{
				"supplier": frappe.db.get_value("Supplier", {"supplier_name": supplier}, "name"),
				"bid_status": "Bid Received",
				"bid_amount": round(estimate * share, -3),
				"programme_weeks": weeks,
				"technically_compliant": compliant,
				"tax_clearance_valid": 1,
				"insurance_valid": compliant,
				"coida_valid": 1,
				"bee_level": "Level 1" if compliant else "Level 4",
				"bid_date": nowdate(),
				"remarks": "" if compliant else "Programme excludes the fence; no proof of insurance.",
			},
		)
	tender.submission_deadline = now_datetime()
	tender.save(ignore_permissions=True)
	tender.submit()
	commercial.set_tender_status(tender.name, "Under Evaluation")
	return tender.name


def _crm():
	if not frappe.db.exists("DocType", "CRM Deal"):
		return "Frappe CRM is not installed on this site (install it from the Marketplace to show the enquiry step)"
	made = []
	try:
		for first, organization in (("Marlene", "Hex Valley Cold Storage"), ("Kagiso", "Klein Karoo Dairies"),
			("Imran", "Atlantis Polymer Works")):
			if not frappe.db.exists("CRM Lead", {"organization": organization}):
				frappe.get_doc({"doctype": "CRM Lead", "first_name": first, "organization": organization,
					"email": f"{first.lower()}@example.com"}).insert(ignore_permissions=True)
				made.append(f"lead {organization}")
		organization = "Riebeek Kasteel Wines"
		if not frappe.db.exists("CRM Organization", organization):
			frappe.get_doc({"doctype": "CRM Organization", "organization_name": organization}).insert(ignore_permissions=True)
		if not frappe.db.exists("CRM Deal", {"organization": organization}):
			statuses = frappe.get_all("CRM Deal Status", pluck="name")
			status = next((s for s in statuses if "Proposal" in s), statuses[0] if statuses else None)
			frappe.get_doc({"doctype": "CRM Deal", "organization": organization, "status": status,
				"fc_template": TEMPLATE, "fc_contract_model": "EPC", "fc_capacity_kwp": 1200,
				"fc_storage_kwh": 2000}).insert(ignore_permissions=True)
			made.append(f"deal {organization} at {status}")
	except Exception:
		frappe.log_error(title="Construction demo: CRM records", message=frappe.get_traceback())
		return "Frappe CRM records could not be created — see the Error Log"
	return ", ".join(made) or "already loaded"
