# Third-party notices

Fuse Construction adapts design and code from the open-source projects below. Each is used
under its own licence; the notice is reproduced here as the licence requires. Files that
contain adapted code say so in their module docstring.

## epcforge — MIT

Source: https://github.com/invento-software-limited/epcforge (commit b373086, 2026-09-15)

Copyright (c) 2026 Invento Software Limited

| Lifted from | Into |
|---|---|
| `doctype/boq` (pricing, milestone payment schedule, material request mapping) | `fuse_construction/fuse_construction/doctype/fc_boq/fc_boq.py`, `fuse_construction/commercial.py` |
| `doctype/boq_group`, `doctype/budget_cost_head` (NestedSet trees) | `doctype/fc_boq_group`, `doctype/fc_cost_head` |
| `doctype/tender`, `tender_bidder`, `tender_document` (fields, status flow, bid counts, lowest bid) | `doctype/fc_tender`, `fc_tender_bidder`, `fc_tender_document` |
| `doctype/document_register` (types, statuses, revisions) | `doctype/fc_document_register` |
| `doctype/project_budget` (EVM fields, CPI/SPI/EAC, health thresholds) | `fuse_construction/maths.py` (`evm`, `health`, `schedule_status`), `doctype/fc_project_budget` |
| `report/tender_summary`, `report/boq_summary`, `report/budget_vs_actual` | `report/fc_tender_summary`, `report/fc_boq_summary`, `report/fc_project_shape` |
| `page/project_dashboard` (layout: contract value, health, procurement coverage, cost by type, milestones, phase progress) | `page/fc_project_dashboard`, `fuse_construction/dashboard.py` |

Not used: epcforge's hooks on ERPNext invoices and payments, and its desk-wide sidebar script —
ERPNext is not the ledger here.

```
MIT License

Copyright (c) 2026 Invento Software Limited

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## construction_management — MIT (ideas only)

Source: https://github.com/mradul010/construction_management (branch version-16)

The running-account (RA bill) line model — previous / this period / to date — informs
`FC Certificate Line`. No code was copied; the model is re-implemented in
`fuse_construction/maths.py` (`certificate_line`, `certificate`).

## Syncflo's own

Award, purchase-order, certificate, valuation and Intacct posting code is adapted from
`fuse_projects` (Syncflo, MIT), as it stood at 0.2.0 (commit d7eb39c) and 0.2.1 (92553f1).
fuse_projects itself is unchanged.

## Not used

`TechwithZakir/Reckon-Constructions` and `zuilsoft03/erpnext_construction_ph` carry no licence
(all rights reserved). They were not read for code and nothing from them is in this app.
