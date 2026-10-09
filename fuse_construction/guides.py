"""The user guides this app ships — one per module, merged onto the Fuse Training page.

WRITTEN in `docs/training/*.md`, SERVED from `public/files/training/*.html`. Built with the
one build tool every Fuse app uses, which lives in the Manufacturing repo:

    python <fuse_manufacturing>/fuse_manufacturing/docs/build_guides.py S:/Products/Fuse/fuse_construction/fuse_construction

The HTML is generated. A hand edit to it is lost on the next build.
"""

# Path is relative to /assets/fuse_construction/files/.
GUIDES = [
	{"title": "Construction: BOQ, Award and Budget", "file": "training/01 BOQ and Budget.html"},
	{"title": "Construction: Project Shape", "file": "training/02 Project Shape.html"},
	{"title": "Construction: Tenders", "file": "training/03 Tenders.html"},
	{"title": "Construction: Subcontracts and Retention", "file": "training/04 Subcontracts and Retention.html"},
	{"title": "Construction: Client Billing", "file": "training/05 Client Billing.html"},
	{"title": "Construction: Site on a Phone", "file": "training/06 Site on a Phone.html"},
	{"title": "Construction: Documents", "file": "training/07 Documents.html"},
]


def get_guides():
	"""This app's guides, for the theme's `fuse_guides` hook. Copies, never the list itself."""
	return [
		{
			"title": guide["title"],
			"url": f"/assets/fuse_construction/files/{guide['file']}",
			"is_pdf": guide["file"].lower().endswith(".pdf"),
		}
		for guide in GUIDES
	]
