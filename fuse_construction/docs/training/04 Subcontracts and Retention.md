# Subcontracts and Retention

*Part payments, advances and staggered retention — Fuse Construction user guide 04*

## The subcontract

A subcontract comes from a tender award or straight from the BOQ. It holds:

- the **scope lines** — quantity × rate, each on a BOQ section;
- the **advance** — a % or amount paid up front, and the % of each certificate that recovers it;
- **retention** — the % held on each certificate, and the **cap** (as a % of the value);
- **release stages** — usually 50% at practical completion and 50% at the end of the defects
  liability period. Any number of stages, adding up to 100%;
- the **payment schedule** — when each payment is expected. Press **Generate Payment
  Schedule**, then adjust it to what was agreed.

Submitting it commits the cost to the job. If FC Settings says so, a matching purchase order
is raised too.

## Paying the advance

**Create → Advance Payment.** The certificate pays the advance and nothing else.

## Monthly certificates

**Create → Progress Certificate.** Every scope line arrives with what was certified before.
For each line enter the **quantity or % done to date** — not this month's work. Fuse works out:

| | |
|---|---|
| This certificate | Work to date less work certified before |
| Retention | The retention % of this certificate, until the cap is reached |
| Advance recovered | The recovery % of this certificate, until the advance is back — and all of it on the certificate that reaches 100% |
| Contra-charges | Add each one with its reason |
| Net payable | What is left |

> **Screenshot: a certificate with retention, recovery and a contra-charge**
> *[FC Subcontract Certificate, Payable section]*

### Approval

Where the approval workflow is on: the QS **Assesses**, the project manager **Approves**
(which submits it), and finance **Releases** it for payment. Release is when it would post to
Intacct, once posting is switched on.

A certificate cannot be cancelled while a later one exists: each builds on the one before.

## Releasing retention

Record **Practical Completion** on the subcontract. Each stage's due date follows (the DLP
stage = practical completion + the DLP months), and a reminder goes to the project managers
before and on the day it falls due.

**Create → Retention Release**, choose the stage. The amount is the stage's share of all
retention held; the last stage releases whatever is left.

## Reports

- **Retention Ledger** — held, released and outstanding, the next stage and when.
- **Subcontract Status** — value, certified, retention, advance, paid.
- **Cash Flow Forecast** — what is due out and in, month by month.
