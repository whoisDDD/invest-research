import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from invest_research.core import Fact, DataError, as_of_facts, ttm, single_quarter, growth

def fact(end, value, pub="2026-10-30",currency="CNY"):
    return Fact("TEST", date.fromisoformat(end), date.fromisoformat(pub),"revenue",D(value),currency,"source","https://example.com")

class CalculationTests(unittest.TestCase):
    def test_ttm_accumulated_not_annualized(self):
        fs=[fact("2025-12-31","120"),fact("2025-09-30","80"),fact("2026-09-30","95")]
        value,_=ttm({f.period_end:f for f in fs},date(2026,9,30))
        self.assertEqual(value,D("135"))

    def test_missing_is_not_zero(self):
        f=fact("2026-09-30","95")
        self.assertIsNone(ttm({f.period_end:f},f.period_end)[0])

    def test_quarter_difference(self):
        a,b=fact("2026-06-30","60"),fact("2026-09-30","95")
        self.assertEqual(single_quarter({f.period_end:f for f in (a,b)},b.period_end),D("35"))

    def test_annual_is_annual(self):
        f=fact("2025-12-31","120")
        self.assertEqual(ttm({f.period_end:f},f.period_end)[0],D("120"))

    def test_revision_available_at_time(self):
        old=fact("2025-12-31","120",pub="2026-03-30")
        new=replace(old,value=D("130"),published_at=date(2026,5,1))
        self.assertEqual(as_of_facts([new,old],date(2026,4,1))[0].value,D("120"))
        self.assertEqual(as_of_facts([new,old],date(2026,6,1))[0].value,D("130"))

    def test_conflicting_revision_rejected(self):
        a=fact("2025-12-31","120")
        with self.assertRaises(DataError):
            as_of_facts([a,replace(a,value=D("130"))],date(2026,11,5))

    def test_negative_base_separate(self):
        self.assertEqual(growth(D("3"),D("-2")),{"value":None,"status":"turnaround"})
        self.assertEqual(growth(D("-4"),D("-2"))["status"],"loss_widening")

    def test_zero_base(self):
        self.assertEqual(growth(D("3"),D("0"))["status"],"zero_base")

    def test_currency_not_silently_mixed(self):
        fs=[fact("2025-12-31","120"),fact("2025-09-30","80"),fact("2026-09-30","95",currency="USD")]
        with self.assertRaises(DataError):
            ttm({f.period_end:f for f in fs},date(2026,9,30))

