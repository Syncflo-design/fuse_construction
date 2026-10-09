"""The hand calculation in docs/hand-calculation.md, run through the real code.

Plain unittest, no site needed:

    python -m unittest discover -s fuse_construction/tests -t .

from the repo root. Every figure asserted here is one written out by hand in the doc; if
the code and the paper ever disagree, this fails.
"""

import datetime
import unittest

from fuse_construction import maths


class Subcontract:
	"""The worked example: R2.4m civils, 10% advance recovered at 20%, 5% retention capped
	at 5% of value, released 50% at practical completion and 50% after a 12-month DLP."""

	VALUE = 2_400_000.00
	ADVANCE = 240_000.00
	RETENTION = 5
	CAP = 120_000.00
	RECOVERY = 20


def run_certificates(to_dates, contras):
	"""Three certificates in sequence, carrying the running totals like the controller does."""
	results = []
	previously, held, recovered = 0.0, 0.0, 0.0
	for to_date, contra in zip(to_dates, contras, strict=True):
		figures = maths.certificate(
			gross_to_date=to_date,
			previously_certified=previously,
			subcontract_value=Subcontract.VALUE,
			retention_percent=Subcontract.RETENTION,
			retention_cap=Subcontract.CAP,
			retention_held_before=held,
			recovery_percent=Subcontract.RECOVERY,
			advance_outstanding=Subcontract.ADVANCE - recovered,
			contra_total=contra,
		)
		results.append(figures)
		previously = figures["gross_to_date"]
		held += figures["retention_this"]
		recovered += figures["advance_recovery_this"]
	return results, held, recovered


class TestWorkedExample(unittest.TestCase):
	def setUp(self):
		self.certs, self.held, self.recovered = run_certificates(
			[720_000, 1_560_000, 2_400_000], [0, 35_000, 0]
		)

	def test_certificate_one(self):
		c = self.certs[0]
		self.assertEqual(c["gross_this"], 720_000.00)
		self.assertEqual(c["retention_this"], 36_000.00)
		self.assertEqual(c["advance_recovery_this"], 144_000.00)
		self.assertEqual(c["net_payable"], 540_000.00)

	def test_certificate_two_recovers_only_what_is_left(self):
		c = self.certs[1]
		self.assertEqual(c["gross_this"], 840_000.00)
		self.assertEqual(c["retention_this"], 42_000.00)
		# 20% of 840,000 is 168,000 but only 96,000 of the advance is still out.
		self.assertEqual(c["advance_recovery_this"], 96_000.00)
		self.assertEqual(c["contra_total"], 35_000.00)
		self.assertEqual(c["net_payable"], 667_000.00)

	def test_certificate_three_reaches_the_cap(self):
		c = self.certs[2]
		self.assertEqual(c["gross_this"], 840_000.00)
		self.assertEqual(c["retention_this"], 42_000.00)
		self.assertEqual(c["advance_recovery_this"], 0.00)
		self.assertEqual(c["net_payable"], 798_000.00)
		self.assertTrue(c["final"])
		self.assertEqual(self.held, 120_000.00)
		self.assertEqual(self.recovered, 240_000.00)

	def test_releases(self):
		first = maths.release_amount(50, self.held, 0, is_last=False)
		second = maths.release_amount(50, self.held, first, is_last=True)
		self.assertEqual(first, 60_000.00)
		self.assertEqual(second, 60_000.00)

	def test_everything_paid_is_value_less_contra(self):
		paid = Subcontract.ADVANCE + sum(c["net_payable"] for c in self.certs) + self.held
		self.assertEqual(maths.money(paid), 2_365_000.00)


class TestCapBinds(unittest.TestCase):
	def test_ten_percent_retention_capped_at_five(self):
		held = 0.0
		retained = []
		for gross in (1_000_000, 1_000_000, 400_000):
			r = maths.retention_for(gross, 10, 120_000, held)
			retained.append(r)
			held += r
		self.assertEqual(retained, [100_000.00, 20_000.00, 0.00])
		self.assertEqual(held, 120_000.00)

	def test_negative_certificate_gives_back_at_most_what_is_held(self):
		self.assertEqual(maths.retention_for(-50_000, 5, 0, 1_000), -1_000.00)
		self.assertEqual(maths.retention_for(-10_000, 5, 0, 1_000), -500.00)


class TestAdvance(unittest.TestCase):
	def test_final_certificate_recovers_everything(self):
		self.assertEqual(maths.advance_recovery_for(100_000, 20, 70_000, final=True), 70_000.00)

	def test_never_more_than_gross(self):
		self.assertEqual(maths.advance_recovery_for(10_000, 20, 70_000, final=True), 10_000.00)

	def test_nothing_on_a_reduction(self):
		self.assertEqual(maths.advance_recovery_for(-10_000, 20, 70_000), 0.0)


class TestClientValuation(unittest.TestCase):
	def test_valuation_with_advance_and_retention(self):
		v = maths.client_valuation(
			gross_to_date=3_425_505,
			previously_valued=0,
			contract_value=63_660_550,
			retention_percent=5,
			retention_cap=0,
			retention_held_before=0,
			advance_percent=10,
			advance_outstanding=6_366_055,
		)
		self.assertEqual(v["retention_this"], 171_275.25)
		self.assertEqual(v["advance_recovery_this"], 342_550.50)
		self.assertEqual(v["net_due"], 2_911_679.25)


class TestTemplateScaling(unittest.TestCase):
	def test_sizes(self):
		self.assertEqual(maths.template_qty("Fixed", 12, 6500, 7000), 12.0)
		self.assertEqual(maths.template_qty("Per kWp", 1.818, 6500, 7000), 11817.0)
		self.assertEqual(maths.template_qty("Per MWp", 1.85, 6500, 7000), 12.025)
		self.assertEqual(maths.template_qty("Per MWh", 1, 6500, 7000), 7.0)
		with self.assertRaises(ValueError):
			maths.template_qty("Per acre", 1, 1, 1)

	def test_build_up(self):
		rate = maths.line_rate(0, {"labour_rate": 210, "plant_rate": 70, "material_rate": 400,
			"subcontract_rate": 80})
		self.assertEqual(rate, 760.00)
		self.assertEqual(maths.line_rate(55.5, {}), 55.50)


class TestLabour(unittest.TestCase):
	def test_nine_hours_is_eight_plus_one(self):
		self.assertEqual(maths.split_overtime([(9, 0)], 8, True), [(8.0, 1.0)])

	def test_split_day_takes_overtime_off_the_last_section(self):
		self.assertEqual(maths.split_overtime([(5, 0), (5, 0)], 8, True), [(5.0, 0.0), (3.0, 2.0)])

	def test_auto_off_leaves_hours_alone(self):
		self.assertEqual(maths.split_overtime([(10, 0)], 8, False), [(10.0, 0.0)])

	def test_rates(self):
		self.assertEqual(maths.labour_rates(100, 1.5, False, 2), (100.00, 150.00))
		self.assertEqual(maths.labour_rates(100, 1.5, True, 2), (200.00, 200.00))


class TestEarnedValue(unittest.TestCase):
	def test_hand_calculation(self):
		e = maths.evm(bac=1_000_000, percent_complete=40, actual=500_000, planned=450_000)
		self.assertEqual(e["earned_value"], 400_000.00)
		self.assertEqual(e["cpi"], 0.8)
		self.assertAlmostEqual(e["spi"], 0.8889, places=4)
		self.assertEqual(e["eac"], 1_250_000.00)
		self.assertEqual(e["etc"], 750_000.00)
		self.assertEqual(e["vac"], -250_000.00)
		self.assertEqual(maths.health(e["cpi"], e["spi"]), "Red")

	def test_nothing_spent(self):
		e = maths.evm(bac=1_000, percent_complete=0, actual=0, planned=0)
		self.assertIsNone(e["cpi"])
		self.assertEqual(e["eac"], 1_000.00)
		self.assertEqual(maths.health(None, None), "Green")

	def test_planned_fraction(self):
		d = datetime.date
		self.assertEqual(maths.planned_fraction(d(2026, 1, 1), d(2026, 1, 10), d(2025, 12, 31)), 0.0)
		self.assertEqual(maths.planned_fraction(d(2026, 1, 1), d(2026, 1, 10), d(2026, 1, 5)), 0.5)
		self.assertEqual(maths.planned_fraction(d(2026, 1, 1), d(2026, 1, 10), d(2026, 2, 1)), 1.0)
		self.assertIsNone(maths.planned_fraction(None, d(2026, 1, 10), d(2026, 1, 5)))

	def test_periods(self):
		d = datetime.date
		weeks = maths.period_ends(d(2026, 10, 7), d(2026, 10, 20), "Weekly")
		self.assertEqual(weeks, [d(2026, 10, 11), d(2026, 10, 18), d(2026, 10, 25)])
		months = maths.period_ends(d(2026, 11, 15), d(2027, 1, 2), "Monthly")
		self.assertEqual(months, [d(2026, 11, 30), d(2026, 12, 31), d(2027, 1, 31)])


class TestPaymentPlan(unittest.TestCase):
	def test_plan_adds_up_to_value(self):
		d = datetime.date
		rows = maths.payment_plan(
			2_400_000, 240_000, 120_000,
			maths.month_ends(d(2026, 11, 1), d(2027, 1, 31)),
			[("Practical completion", 50, d(2027, 1, 31)), ("End of DLP", 50, d(2028, 1, 31))],
		)
		self.assertEqual(maths.money(sum(r["amount"] for r in rows)), 2_400_000.00)
		self.assertEqual([r["payment_type"] for r in rows],
			["Advance", "Monthly Progress", "Monthly Progress", "Monthly Progress",
			 "Retention Release", "Retention Release"])
		self.assertEqual(rows[1]["amount"], 680_000.00)


if __name__ == "__main__":
	unittest.main()
