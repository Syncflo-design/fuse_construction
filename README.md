# Fuse Construction

Construction for Fuse: bills of quantities, tenders, subcontracts, retention, site labour and
"project shape" (budget against committed, actual and earned value), with **Sage Intacct as the
ledger**. Built for NSE Energy (C&I solar PV + battery storage, EPC and IPP), usable by any
contractor on Fuse.

Frappe / ERPNext v16. Requires `erpnext` and `fuse_core`. Works with or without
`fuse_projects`, `fuse_manufacturing` and Frappe CRM — it uses their screens and fields where
they are installed and never changes their doctypes.

## Rules this app keeps

- **Its own doctypes, all prefixed `FC`.** No Fuse Manufacturing or Fuse Projects doctype is
  touched. ERPNext documents only gain `fc_` custom fields (listed in `install.py`).
- **Intacct is the ledger.** No ERPNext Sales or Purchase Invoice is raised. Certificates,
  valuations and retention releases post to Intacct as AP bills / AR invoices — **only** when
  "Post Construction Documents to Intacct" is ticked in FC Settings (off by default) and the
  Intacct connection is enabled. With it off, no Intacct call is made.
- **Intacct first** when posting is on: the posting happens before the local status moves, and
  a rejection rolls the document back. Deterministic control IDs (fuse_core) stop a double post.

## What is in it

| Area | Doctypes / screens |
|---|---|
| Estimating | FC BOQ (submittable, revisions by amend), FC BOQ Item, FC BOQ Section (programme), FC BOQ Group (tree), FC BOQ Template (sized per kWp / MWp / kWh / MWh), FC Cost Head (tree) |
| Award | One button: project + a task per section + FC Project Budget. Awards into an existing project (e.g. one mirrored from Intacct) when chosen. |
| Cost control | FC Project Budget (snapshot), FC Budget Revision (the only way a budget moves after award), FC Progress Update (dated progress log), report **FC Project Shape** (section table + PV/EV/AC/committed curve + portfolio view), page **fc-project-dashboard** |
| Tenders | FC Tender, bidders with compliance, award → draft subcontract or purchase order |
| Subcontracts | FC Subcontract (advance, recovery, retention with cap, staggered release stages, payment schedule, optional mirror PO), FC Subcontract Certificate (running-account lines, contra-charges, approval workflow), FC Retention Release |
| Client billing | FC Client Valuation (measured, milestone or advance), client retention and release |
| Site (phone) | page **fuse-site**: crew time, approve time, progress, daily report with photos and signature, material request, receive delivery. FC Crew Timesheet → one ERPNext Timesheet per worker on approval. FC Daily Site Report. |
| Documents | FC Document Register (revisions by amend) |
| Reports | Project Shape, Retention Ledger, Subcontract Status, Tender Summary, BOQ Summary, Crew Hours, Payroll Hours Export, Cash Flow Forecast |

## Install

1. Push the repo, add it to the bench (Frappe Cloud → Apps → Add from GitHub), **Deploy** (not
   just Update — Update skips `bench build`, so the phone page's CSS/JS would be stale).
2. Install on the site. `after_install` creates the custom fields, seeds the section and cost-head
   lists, creates the certificate approval workflow, builds the Construction workspace and adds
   the six module switches to Active Modules.
3. If `after_migrate` did not fire, run **`fuse_construction.api.setup`** as System Manager.
4. Open **FC Settings**: default company, default activity type, the subcontract and quotation
   items, the site warehouse.

## Demo

FC BOQ list → menu → **Load Construction Demo** (System Manager). See `demo/nse.py` for what it creates.
Back up the outgoing demo profile first (`S:\Products\Fuse\demo_profiles\PROFILES.md`).

## Checks

```
python -m unittest discover -s fuse_construction/tests -t .
python -m ruff check .
```

The tests are the worked example in `docs/hand-calculation.md`, run through `maths.py`.

## Phase 2 (built, switched off)

`fuse_construction/intacct/` — award to Intacct PROJECT/TASK, AP bills, AR invoices, release
postings, nightly paid-status read. Shapes for certificates and valuations come from
fuse_projects 0.2.0 (d7eb39c); the advance, release and paid-status shapes are new and must be
proved with `gateway.lookup` on a test company before posting is switched on.
