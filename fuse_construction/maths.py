"""The construction arithmetic, with no Frappe and no database.

Every function here is pure: the same inputs always give the same answer. That is what lets
the retention, advance and certificate maths be checked against a hand calculation on any
machine in a second (tests/test_maths.py, docs/hand-calculation.md) — the numbers a
subcontractor is paid should never depend on a site being up to prove them.

Money is rounded half-up to cents at every step that produces an amount someone will see,
the way a QS rounds on paper. Rounding only at the end would let a certificate's lines
disagree with its total by a cent.
"""

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

# ──────────────────────────────────────────────────────────────────────────────
# Money
# ──────────────────────────────────────────────────────────────────────────────


def num(value):
	"""A float from anything a form might hold: None, "", a string, a Decimal."""
	if value in (None, ""):
		return 0.0
	return float(value)


def money(value):
	return float(Decimal(str(num(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def qty(value):
	return float(Decimal(str(num(value))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def pct_of(amount, percent):
	return money(num(amount) * num(percent) / 100)


# ──────────────────────────────────────────────────────────────────────────────
# BOQ
# ──────────────────────────────────────────────────────────────────────────────

BUILD_UP = ("labour_rate", "plant_rate", "material_rate", "subcontract_rate")

# What one unit of each basis is measured in, relative to the BOQ's kWp / kWh fields.
QTY_BASIS = {
	"Fixed": (None, 1),
	"Per kWp": ("kwp", 1),
	"Per MWp": ("kwp", 1 / 1000),
	"Per kWh": ("kwh", 1),
	"Per MWh": ("kwh", 1 / 1000),
}


def line_rate(rate, build_up):
	"""A line's cost rate: the build-up when one is entered, else the rate as typed."""
	built = sum(num(build_up.get(field)) for field in BUILD_UP)
	return money(built) if built else money(rate)


def template_qty(basis, factor, kwp, kwh):
	"""A template line's quantity for a plant of this size.

	Unknown bases are refused rather than treated as fixed: a line that silently stops
	scaling prices a 20 MW plant like a 1 MW one.
	"""
	if basis not in QTY_BASIS:
		raise ValueError(f"Unknown quantity basis {basis!r}")
	size, scale = QTY_BASIS[basis]
	if size is None:
		return qty(factor)
	return qty(num(factor) * num(kwp if size == "kwp" else kwh) * scale)


def sell_value(cost, markup_percent):
	return money(num(cost) * (1 + num(markup_percent) / 100))


# ──────────────────────────────────────────────────────────────────────────────
# Retention and advances
# ──────────────────────────────────────────────────────────────────────────────


def retention_for(gross_this, percent, cap, held_before):
	"""Retention to hold on one certificate (or valuation).

	`cap` is the most that may ever be held in total; 0 or None means no cap. Once the cap is
	reached nothing more is held. A certificate that takes value back (negative gross) gives
	back retention in proportion, but never more than is actually held.
	"""
	gross_this, held_before, cap = num(gross_this), num(held_before), num(cap)
	retention = pct_of(gross_this, percent)
	if gross_this < 0:
		return money(max(retention, -held_before))
	if cap > 0:
		retention = min(retention, max(money(cap - held_before), 0.0))
	return money(retention)


def advance_recovery_for(gross_this, percent, outstanding, final=False):
	"""How much of an advance one certificate recovers.

	A fixed % of the gross until the advance is recovered. On the certificate that takes the
	work to 100% whatever is still outstanding comes back in full — an advance must never
	outlive the work it was paid against. Never more than the gross itself, so a recovery
	cannot turn a certificate into a demand for money.
	"""
	gross_this, outstanding = num(gross_this), num(outstanding)
	if gross_this <= 0 or outstanding <= 0:
		return 0.0
	if final:
		return money(min(outstanding, gross_this))
	return money(min(pct_of(gross_this, percent), outstanding, gross_this))


def release_amount(share_percent, held_total, released_before, is_last):
	"""What one release stage pays out.

	`share_percent` of everything held to date, never more than is still outstanding. The
	last stage releases whatever is left, so rounding — or retention held after an earlier
	stage was released — can never leave a few cents stranded with nobody due to pay them.
	"""
	outstanding = money(num(held_total) - num(released_before))
	if outstanding <= 0:
		return 0.0
	if is_last:
		return outstanding
	return money(min(pct_of(held_total, share_percent), outstanding))


# ──────────────────────────────────────────────────────────────────────────────
# Subcontract certificates — the running-account model
# ──────────────────────────────────────────────────────────────────────────────


def certificate_line(contract_qty, rate, previous_qty, previous_amount, to_date_qty):
	"""One measured line: what is done to date, and what this certificate adds."""
	contract_qty, to_date_qty = num(contract_qty), num(to_date_qty)
	to_date_amount = money(to_date_qty * num(rate))
	return {
		"to_date_qty": qty(to_date_qty),
		"to_date_percent": round(to_date_qty / contract_qty * 100, 4) if contract_qty else 0.0,
		"to_date_amount": to_date_amount,
		"this_qty": qty(to_date_qty - num(previous_qty)),
		"this_amount": money(to_date_amount - num(previous_amount)),
	}


def certificate(
	*,
	gross_to_date,
	previously_certified,
	subcontract_value,
	retention_percent,
	retention_cap,
	retention_held_before,
	recovery_percent,
	advance_outstanding,
	contra_total,
):
	"""The money on one progress certificate.

	Gross this certificate is the movement in the cumulative valuation, so an error in an
	earlier certificate corrects itself on the next one instead of compounding.
	"""
	gross_to_date = money(gross_to_date)
	gross_this = money(gross_to_date - num(previously_certified))
	final = num(subcontract_value) > 0 and gross_to_date >= money(subcontract_value)

	retention = retention_for(gross_this, retention_percent, retention_cap, retention_held_before)
	recovery = advance_recovery_for(gross_this, recovery_percent, advance_outstanding, final=final)
	contra = money(contra_total)

	return {
		"gross_to_date": gross_to_date,
		"gross_this": gross_this,
		"retention_this": retention,
		"advance_recovery_this": recovery,
		"contra_total": contra,
		"net_payable": money(gross_this - retention - recovery - contra),
		"percent_certified": round(gross_to_date / num(subcontract_value) * 100, 2)
		if num(subcontract_value)
		else 0.0,
		"final": final,
	}


def client_valuation(
	*,
	gross_to_date,
	previously_valued,
	contract_value,
	retention_percent,
	retention_cap,
	retention_held_before,
	advance_percent,
	advance_outstanding,
):
	"""The money on one client valuation. Same shape as a certificate, the other way round.

	The client's advance is recovered in the same proportion it was paid: an advance of 10%
	of the contract comes back as 10% of each valuation, and in full on the valuation that
	reaches the contract value.
	"""
	gross_to_date = money(gross_to_date)
	gross_this = money(gross_to_date - num(previously_valued))
	final = num(contract_value) > 0 and gross_to_date >= money(contract_value)

	retention = retention_for(gross_this, retention_percent, retention_cap, retention_held_before)
	recovery = advance_recovery_for(gross_this, advance_percent, advance_outstanding, final=final)
	return {
		"gross_to_date": gross_to_date,
		"gross_this": gross_this,
		"retention_this": retention,
		"advance_recovery_this": recovery,
		"net_due": money(gross_this - retention - recovery),
		"final": final,
	}


# ──────────────────────────────────────────────────────────────────────────────
# Payment schedule
# ──────────────────────────────────────────────────────────────────────────────


def month_ends(start, end):
	"""The last day of every month from start's to end's, inclusive."""
	start, end = to_date(start), to_date(end)
	if not start or not end or end < start:
		return []
	out = []
	year, month = start.year, start.month
	while (year, month) <= (end.year, end.month):
		out.append(datetime.date(year, month, calendar.monthrange(year, month)[1]))
		month += 1
		if month > 12:
			year, month = year + 1, 1
	return out


def payment_plan(value, advance, retention_total, progress_dates, stages):
	"""Planned payments that add up to the subcontract value exactly.

	The advance up front; the rest of the value less retention spread evenly over the months
	of the work (the last month takes the rounding); retention back in its release stages.
	`stages` is [(name, share_percent, planned_date)].
	"""
	value, advance, retention_total = money(value), money(advance), money(retention_total)
	rows = []
	if advance > 0:
		rows.append({"payment_type": "Advance", "description": "Advance", "amount": advance,
			"planned_date": progress_dates[0] if progress_dates else None})

	progress_total = money(value - advance - retention_total)
	if progress_dates and progress_total > 0:
		each = money(progress_total / len(progress_dates))
		for index, date in enumerate(progress_dates):
			amount = each if index < len(progress_dates) - 1 else money(progress_total - each * index)
			rows.append({"payment_type": "Monthly Progress",
				"description": f"Progress {date.strftime('%b %Y')}", "amount": amount,
				"planned_date": date})

	released = 0.0
	for index, (name, share, date) in enumerate(stages):
		amount = (
			money(retention_total - released)
			if index == len(stages) - 1
			else pct_of(retention_total, share)
		)
		released = money(released + amount)
		if amount > 0:
			rows.append({"payment_type": "Retention Release", "description": name, "amount": amount,
				"planned_date": date})
	return rows


# ──────────────────────────────────────────────────────────────────────────────
# Labour
# ──────────────────────────────────────────────────────────────────────────────


def split_overtime(rows, standard_hours, auto):
	"""Move one worker's hours past the standard day into overtime.

	`rows` is that worker's rows for one day, [(normal, overtime)], possibly over several
	sections. The excess comes off the LAST rows first — the overtime was worked at the end of
	the day, on whatever the crew moved to last. Returns new tuples; never edits the input.
	"""
	out = [[num(n), num(o)] for n, o in rows]
	if not auto or not num(standard_hours):
		return [tuple(r) for r in out]
	excess = sum(r[0] for r in out) - num(standard_hours)
	for row in reversed(out):
		if excess <= 0:
			break
		move = min(row[0], excess)
		row[0] -= move
		row[1] += move
		excess -= move
	return [(qty(n), qty(o)) for n, o in out]


def labour_rates(rate, overtime_multiplier, sunday, sunday_multiplier):
	"""(normal rate, overtime rate) for one worker on one day."""
	rate = num(rate)
	base = num(sunday_multiplier) if sunday and num(sunday_multiplier) > 1 else 1.0
	overtime = max(num(overtime_multiplier) or 1.0, base)
	return money(rate * base), money(rate * overtime)


# ──────────────────────────────────────────────────────────────────────────────
# Earned value
# ──────────────────────────────────────────────────────────────────────────────


def to_date(value):
	if not value:
		return None
	if isinstance(value, datetime.datetime):
		return value.date()
	if isinstance(value, datetime.date):
		return value
	return datetime.date.fromisoformat(str(value)[:10])


def planned_fraction(start, end, as_at):
	"""How much of a section's window has passed — the straight-line baseline.

	Inclusive of both ends, so a one-day task is fully planned on its day. None when the
	section has no dates; the caller decides what that means.
	"""
	start, end, as_at = to_date(start), to_date(end), to_date(as_at)
	if not start or not end:
		return None
	if end < start:
		start, end = end, start
	if as_at < start:
		return 0.0
	if as_at >= end:
		return 1.0
	return ((as_at - start).days + 1) / ((end - start).days + 1)


def evm(bac, percent_complete, actual, planned):
	"""Earned value for one section or a whole job.

	CPI and SPI are None where they cannot be measured (nothing spent, nothing planned yet)
	rather than a made-up 1.0, so a report can say so. EAC assumes the rest of the work goes
	at the rate the job is actually running at; before any work is earned it falls back to
	what has been spent plus the budget still to spend.
	"""
	return evm_values(bac, pct_of(bac, percent_complete), actual, planned)


def evm_values(bac, earned, actual, planned):
	"""The same as evm(), from an earned value already summed — a job's total is the sum of
	its sections' earned value, not its overall percent applied to its budget."""
	bac, earned, actual, planned = num(bac), money(earned), num(actual), num(planned)
	cpi = round(earned / actual, 4) if actual else None
	spi = round(earned / planned, 4) if planned else None

	if cpi:
		eac = money(bac / cpi)
	elif actual:
		eac = money(actual + bac - earned)
	else:
		eac = money(bac)

	return {
		"earned_value": earned,
		"planned_value": money(planned),
		"actual_cost": money(actual),
		"cost_variance": money(earned - actual),
		"schedule_variance": money(earned - planned),
		"cpi": cpi,
		"spi": spi,
		"eac": eac,
		"etc": money(eac - actual),
		"vac": money(bac - eac),
	}


def health(cpi, spi):
	"""Green, Amber or Red. Thresholds as epcforge's budget health.

	Unmeasured indices count as on target: a job that has spent nothing is not over budget.
	"""
	c = 1.0 if cpi is None else cpi
	s = 1.0 if spi is None else spi
	if c >= 1.0 and s >= 0.9:
		return "Green"
	if c >= 0.85 and s >= 0.75:
		return "Amber"
	return "Red"


def schedule_status(spi, completed=False):
	if completed:
		return "Completed"
	s = 1.0 if spi is None else spi
	if s >= 1.0:
		return "On Track"
	if s >= 0.85:
		return "Delayed"
	return "Severely Delayed"


def period_ends(start, end, periodicity):
	"""Reporting dates from start to end: Sundays for Weekly, month ends for Monthly."""
	start, end = to_date(start), to_date(end)
	if not start or not end or end < start:
		return []
	if periodicity == "Monthly":
		return month_ends(start, end)
	first = start + datetime.timedelta(days=(6 - start.weekday()))
	out = []
	day = first
	while day < end:
		out.append(day)
		day += datetime.timedelta(days=7)
	out.append(day)
	return out
