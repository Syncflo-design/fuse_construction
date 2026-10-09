# Hand calculation — subcontract, certificates, retention, advance

The worked example from the build plan (§5.5 "Done when"), done on paper. Every figure below
is asserted by `fuse_construction/tests/test_maths.py` against the code in
`fuse_construction/maths.py` — run `python -m unittest discover -s fuse_construction/tests -t .`.

## Terms

| Term | Value |
|---|---|
| Subcontract value | R 2,400,000.00 (civils) |
| Advance | 10% = **R 240,000.00**, paid up front |
| Advance recovery | 20% of each certificate's gross, until recovered; all of what is left on the certificate that reaches 100% |
| Retention | 5% of each certificate's gross |
| Retention cap | 5% of value = **R 120,000.00** |
| Release | 50% at practical completion, 50% at the end of a 12-month defects liability period (the last stage releases whatever is left) |

## Advance payment certificate

Net payable = advance = **R 240,000.00**. (Posts, when posting is on, to Subcontractor Advances.)

## Certificate 1 — 30% to date

| | |
|---|---|
| Certified to date | 2,400,000 × 30% = 720,000.00 |
| Previously certified | 0.00 |
| **Gross this certificate** | **720,000.00** |
| Retention 5% | 36,000.00 (held to date 36,000 ≤ cap 120,000) |
| Advance recovery 20% | 144,000.00 (outstanding before: 240,000) |
| Contra-charges | 0.00 |
| **Net payable** | 720,000 − 36,000 − 144,000 = **540,000.00** |

Advance outstanding after: 240,000 − 144,000 = 96,000.

## Certificate 2 — 65% to date, with a contra-charge

| | |
|---|---|
| Certified to date | 2,400,000 × 65% = 1,560,000.00 |
| Previously certified | 720,000.00 |
| **Gross this certificate** | **840,000.00** |
| Retention 5% | 42,000.00 (held to date 78,000 ≤ 120,000) |
| Advance recovery | 20% would be 168,000.00, but only **96,000.00** is outstanding |
| Contra-charge | 35,000.00 (water bowser hire) |
| **Net payable** | 840,000 − 42,000 − 96,000 − 35,000 = **667,000.00** |

## Certificate 3 — 100% to date

| | |
|---|---|
| Certified to date | 2,400,000.00 |
| Previously certified | 1,560,000.00 |
| **Gross this certificate** | **840,000.00** |
| Retention 5% | 42,000.00 → held to date 120,000.00 = the cap |
| Advance recovery | 0.00 (nothing outstanding) |
| **Net payable** | **798,000.00** |

## Retention releases

| Release | Calculation | Amount |
|---|---|---|
| Practical completion (50%) | 50% × 120,000 held | **60,000.00** |
| End of DLP (50%, last stage) | everything left: 120,000 − 60,000 | **60,000.00** |

## Proof

Advance 240,000 + certificates 540,000 + 667,000 + 798,000 + releases 120,000
= **2,365,000.00** = subcontract value 2,400,000 − contra-charge 35,000. ✔

## When the cap binds

10% retention capped at 5% of R 2,400,000 (R 120,000), certificates of R 1,000,000, R 1,000,000
and R 400,000:

| Certificate | 10% of gross | Held before | Retained | Held after |
|---|---|---|---|---|
| 1 | 100,000 | 0 | 100,000 | 100,000 |
| 2 | 100,000 | 100,000 | **20,000** (cap) | 120,000 |
| 3 | 40,000 | 120,000 | **0** | 120,000 |

## Client valuation (same maths, the other way)

Contract value R 63,660,550; 10% client advance (R 6,366,055 outstanding); 5% retention, no
cap. Valuation 1 values R 3,425,505:

| | |
|---|---|
| Retention 5% | 171,275.25 |
| Advance recovered 10% | 342,550.50 |
| **Net due** | 3,425,505 − 171,275.25 − 342,550.50 = **2,911,679.25** |

## Earned value

Budget at completion R 1,000,000; 40% complete; actual R 500,000; planned R 450,000.

| | |
|---|---|
| EV | 1,000,000 × 40% = 400,000 |
| CPI | 400,000 / 500,000 = **0.80** |
| SPI | 400,000 / 450,000 = **0.8889** |
| EAC | 1,000,000 / 0.80 = **1,250,000** |
| ETC | 1,250,000 − 500,000 = 750,000 |
| VAC | 1,000,000 − 1,250,000 = **−250,000** |
| Health | CPI < 0.85 → **Red** |

Planned value is linear across each section's baseline window, inclusive of both ends: a
section planned 1–10 January is 50% planned on 5 January.

## Labour

Standard day 8 h, overtime ×1.5, Sunday ×2, a worker at R 100/h:

| Day | Booked | Becomes | Cost |
|---|---|---|---|
| Weekday | 9 h | 8 normal + 1 overtime | 8 × 100 + 1 × 150 = R 950 |
| Weekday, split | 5 h section A + 5 h section B | A: 5 normal; B: 3 normal + 2 overtime | A R 500, B R 600 |
| Sunday | 8 h | 8 at ×2 | R 1,600 |
