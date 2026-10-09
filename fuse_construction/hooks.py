app_name        = "fuse_construction"
app_title       = "Fuse Construction"
app_publisher   = "Syncflo"
app_description = "Construction for Fuse — BOQ, tenders, subcontracts, retention, site labour and project shape, with Sage Intacct as the ledger."
app_email       = "ops@syncflo.co.za"
app_license     = "MIT"

# ERPNext for Project, Task, Timesheet and buying; fuse_core for the module switches, the
# tiles and the Intacct gateway. Deliberately NOT fuse_projects or fuse_manufacturing: this
# app installs and works on a Fuse site with neither, and uses their screens where present.
required_apps = ["erpnext", "fuse_core"]

# Both, and fuse_construction.api.setup as well: after_migrate has been seen not to fire on a
# Frappe Cloud deploy. Everything in after_install is idempotent.
after_install = "fuse_construction.install.after_install"
after_migrate = "fuse_construction.install.after_install"

# How this app reaches Fuse: its switches (Active Modules on Intacct Settings), its tiles on
# Fuse Home, and its guides on the Training page. Callables, so the hook values merge as
# plain strings.
fuse_modules = ["fuse_construction.registry.get_modules"]
fuse_tiles = ["fuse_construction.registry.get_tiles"]
fuse_guides = ["fuse_construction.guides.get_guides"]

# Tells the desk whether this is the Fuse demo site, so the demo loader's menu item appears
# there and on no client's site.
extend_bootinfo = "fuse_construction.demo.nse.boot"

# Nothing here posts through a transaction definition (bills and invoices are generic
# objects), so there is nothing for the client to map on the Transactions table.
fuse_processes = []

# Reading, not refusing. Every handler queues a budget refresh or fills a blank section on a
# receipt line; none of them changes how an ERPNext document behaves.
_refresh = "fuse_construction.events.refresh_projects"
doc_events = {
	"Purchase Receipt": {
		"validate": "fuse_construction.events.purchase_receipt_validate",
		"on_submit": _refresh,
		"on_cancel": _refresh,
	},
	"Purchase Order": {
		"on_submit": _refresh,
		"on_cancel": _refresh,
		"on_update_after_submit": _refresh,
	},
	"Stock Entry": {
		"on_submit": _refresh,
		"on_cancel": _refresh,
	},
	"Timesheet": {
		"on_submit": _refresh,
		"on_cancel": _refresh,
	},
	# Every progress change is logged with its date, so earned value can be drawn as a curve.
	"Task": {
		"on_update": "fuse_construction.progress.on_task_update",
	},
	# Frappe CRM, where installed. On a site without it this never fires.
	"CRM Deal": {
		"on_update": "fuse_construction.crm.on_deal_update",
	},
	# A module switched on or off: the workspace follows.
	"Intacct Settings": {
		"on_update": "fuse_construction.events.intacct_settings_updated",
	},
}

scheduler_events = {
	"daily": [
		"fuse_construction.retention.daily",
		"fuse_construction.costing.refresh_all",
	],
	# Stands down silently while posting to Intacct is off.
	"daily_long": [
		"fuse_construction.intacct.paid.scheduled",
	],
}

doctype_js = {
	"Project": "public/js/project.js",
}
