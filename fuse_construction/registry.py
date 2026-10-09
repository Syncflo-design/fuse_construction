"""What this app contributes to Fuse: its switches and its two tiles.

Kept apart from install.py: these are read on every Fuse Home load, by other apps, and that
call has no business importing workspace-building code.

The keys are permanent. Renaming one orphans a client's saved setting and silently switches
the module back on.
"""

MODULES = [
	{
		"key": "fc_boq_budget",
		"label": "Construction: BOQ and Budget",
		"description": "Bills of quantities, templates, award, budgets and project shape. "
		"Off hides the Construction tile.",
	},
	{
		"key": "fc_tenders",
		"label": "Construction: Tenders",
		"description": "Tendering packages to subcontractors and suppliers.",
	},
	{
		"key": "fc_subcontracts",
		"label": "Construction: Subcontracts",
		"description": "Subcontracts, payment schedules, certificates, advances and retention.",
	},
	{
		"key": "fc_client_billing",
		"label": "Construction: Client Billing",
		"description": "Valuations and milestone billing to the client, and client retention.",
	},
	{
		"key": "fc_site",
		"label": "Construction: Site (mobile)",
		"description": "The Site phone screen: crew time, approvals, progress, daily reports, "
		"material requests and deliveries.",
	},
	{
		"key": "fc_documents",
		"label": "Construction: Documents",
		"description": "The project document register — drawings, RFIs, NCRs, transmittals.",
	},
]

# Lucide "hard-hat" and "smartphone", for when Fuse Home draws stroked icons. Until then it
# draws the emoji, which is why both are given.
HARD_HAT = (
	'<path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"></path>'
	'<path d="M14 6a6 6 0 0 1 6 6v3"></path>'
	'<path d="M4 15v-3a6 6 0 0 1 6-6"></path>'
	'<rect x="2" y="15" width="20" height="4" rx="1"></rect>'
)
PHONE = '<rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><path d="M12 18h.01"></path>'

ROLES = ["Projects User", "Projects Manager", "Purchase Manager", "Accounts Manager", "System Manager"]


def get_modules():
	return [dict(module) for module in MODULES]


# ──────────────────────────────────────────────────────────────────────────────
# The Construction desk page
# ──────────────────────────────────────────────────────────────────────────────

# The workspace a construction login lands on (its default workspace). install.py builds it.
WORKSPACE = "Fuse Construction"

# Lucide icons, inner SVG only — fuse_theme wraps them.
CHART = '<path d="M3 3v16a2 2 0 0 0 2 2h16"></path><path d="M18 17V9"></path><path d="M13 17V5"></path><path d="M8 17v-3"></path>'
DASHBOARD = (
	'<rect width="7" height="9" x="3" y="3" rx="1"></rect><rect width="7" height="5" x="14" y="3" rx="1"></rect>'
	'<rect width="7" height="9" x="14" y="12" rx="1"></rect><rect width="7" height="5" x="3" y="16" rx="1"></rect>'
)
CALCULATOR = (
	'<rect width="16" height="20" x="4" y="2" rx="2"></rect><line x1="8" x2="16" y1="6" y2="6"></line>'
	'<line x1="16" x2="16" y1="14" y2="18"></line><path d="M16 10h.01"></path><path d="M12 10h.01"></path>'
	'<path d="M8 10h.01"></path><path d="M12 14h.01"></path><path d="M8 14h.01"></path><path d="M12 18h.01"></path>'
	'<path d="M8 18h.01"></path>'
)
GAVEL = (
	'<path d="m14 13-8.381 8.38a1 1 0 0 1-3.001-3l8.384-8.381"></path><path d="m16 16 6-6"></path>'
	'<path d="m21.5 10.5-8-8"></path><path d="m8 8 6-6"></path><path d="m8.5 7.5 8 8"></path>'
)
HANDSHAKE = (
	'<path d="m11 17 2 2a1 1 0 1 0 3-3"></path>'
	'<path d="m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81'
	'a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4"></path>'
	'<path d="m21 3 1 11h-2"></path><path d="M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3"></path><path d="M3 4h8"></path>'
)
FILE_CHECK = (
	'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path>'
	'<path d="M14 2v4a2 2 0 0 0 2 2h4"></path><path d="m9 15 2 2 4-4"></path>'
)
RECEIPT = (
	'<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"></path>'
	'<path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"></path><path d="M12 17.5v-11"></path>'
)
HAND_COINS = (
	'<path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"></path>'
	'<path d="m7 21 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.75-2.91l-4.2 3.9"></path>'
	'<path d="m2 16 6 6"></path><circle cx="16" cy="9" r="2.9"></circle><circle cx="6" cy="5" r="3"></circle>'
)
CLOCK = '<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>'
CLIPBOARD = (
	'<rect width="8" height="4" x="8" y="2" rx="1" ry="1"></rect>'
	'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>'
	'<path d="M12 11h4"></path><path d="M12 16h4"></path><path d="M8 11h.01"></path><path d="M8 16h.01"></path>'
)
FOLDER = (
	'<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5'
	'a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"></path>'
)

# Keyed by the shortcut LABEL in install._shortcuts — rename one, rename both. A label
# with no entry here still works; it is drawn as a plain Frappe shortcut.
DESK_TILES = {
	"Project Shape": {"svg": CHART, "blurb": "Every job's budget, spend and forecast"},
	"Dashboard": {"svg": DASHBOARD, "blurb": "One job's cost, programme and curve"},
	"BOQs": {"svg": CALCULATOR, "blurb": "Estimate, price and award jobs"},
	"Tenders": {"svg": GAVEL, "blurb": "Packages out to subcontractors and suppliers"},
	"Subcontracts": {"svg": HANDSHAKE, "blurb": "Subcontract orders and their running accounts"},
	"Certificates": {"svg": FILE_CHECK, "blurb": "Assess and approve what subcontractors claim"},
	"Valuations": {"svg": RECEIPT, "blurb": "Bill the client by measure or milestone"},
	"Retention": {"svg": HAND_COINS, "blurb": "Held both ways, and when it falls due"},
	"Site": {"svg": PHONE, "blurb": "Crew time, progress and reports on a phone"},
	"Crew Time": {"svg": CLOCK, "blurb": "Approve crews' hours onto the job"},
	"Daily Reports": {"svg": CLIPBOARD, "blurb": "Weather, labour, plant and issues, each day"},
	"Documents": {"svg": FOLDER, "blurb": "Drawings, RFIs, NCRs and transmittals"},
}


def get_desk_tiles():
	"""fuse_theme's fuse_desk_tiles hook: how this app's desk page draws its shortcuts."""
	return {WORKSPACE: {label: dict(tile) for label, tile in DESK_TILES.items()}}


def get_tiles():
	return [
		{
			"key": "fc_construction",
			"module": "fc_boq_budget",
			"label": "Construction",
			"blurb": "BOQs, subcontracts, retention and project shape",
			"icon": "🏗",
			"svg": HARD_HAT,
			# The workspace SLUG — the ["Workspaces", name] form renders as empty skeletons.
			"route": ["fuse-construction"],
			"roles": ROLES,
		},
		{
			"key": "fc_site",
			"module": "fc_site",
			"label": "Site",
			"blurb": "Crew time, progress and daily reports, on a phone",
			"icon": "📱",
			"svg": PHONE,
			"route": ["fuse-site"],
			"requires_page": "fuse-site",
			"roles": ["Projects User", "Projects Manager", "System Manager"],
		},
	]
