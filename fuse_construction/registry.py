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
