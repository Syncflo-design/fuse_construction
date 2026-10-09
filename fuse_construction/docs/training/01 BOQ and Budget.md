# BOQ, Award and Budget

*Pricing a job, opening it, and the budget it is measured against — Fuse Construction user guide 01*

## What the BOQ is for

The bill of quantities is the price of the job, section by section. Once it is awarded it is
also the job's **budget**: everything spent, committed and earned is measured against it.

A BOQ moves through three steps:

| Status | Meaning |
|---|---|
| Draft | Being priced. Change anything. |
| Submitted | The price is agreed. Lines are locked. |
| Awarded | The project is open, with a task per section, and the cost is its budget. |

## Pricing from a template

The same kind of plant is built again and again, so a template carries the lines once and
sizes them to each job.

1. **Construction → BOQs → New.**
2. Enter the **Job Name**, choose **Model** (EPC for a client, IPP for the company's own plant)
   and, for EPC, the **Client**.
3. Choose the **Template** and enter the plant size: **PV Capacity (kWp)** and **Storage (kWh)**.
4. Press **Apply Template**. Every line arrives with its quantity worked out: a line priced
   "per kWp" multiplies by the PV size, "per kWh" by the storage, "Fixed" stays as it is.
5. Check the lines and the **Margin on Cost**. Save.

The **Project Code** is the job's code in Intacct. Leave it empty and one is numbered for you.

> **Screenshot: a BOQ after Apply Template**
> *[BOQ form, Bill of Quantities tab, showing lines sized to 6.5 MWp + 7 MWh]*

### Rate build-up

Open a line's **Rate Build-up** and fill in labour, plant, material and subcontract. They add
up to the line's rate.

### Sections and programme

Each section of the BOQ gets a row under **Sections and Programme** with its budget, contract
value and planned dates (taken from the template's programme and the BOQ's start date). Adjust
the dates if the programme differs — they are the baseline that planned value is measured
against.

## Revising before award

Cancel the submitted BOQ and press **Amend**. The amendment keeps the history and counts the
revision.

## Awarding

On a submitted BOQ press **Award**. Fuse:

- opens a **Project** (or uses the one you chose in the Project field — for example one already
  brought across from Intacct),
- creates a **Task per section**, on the planned dates,
- creates the **FC Project Budget** from the BOQ's cost.

An awarded BOQ cannot be cancelled: it is the baseline.

## Changing the budget after award

Use **Create → Budget Revision**. It starts with every section's current budget; enter the
change against the sections that move and give the reason. Submitting approves it. A
**Transfer between Sections** must add up to zero.

## From the BOQ

| Create | What it makes |
|---|---|
| Tender | A tender for one section, scope and estimate filled in |
| Subcontract | A subcontract for one section, without tendering |
| Material Request | A request for the material lines that are purchasable items |
| Quotation | A quotation for the client, by section or as a lump sum |
| Client Valuation | The next valuation to the client |
