"""Модульные тесты слоя бизнес-логики (unittest)."""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from models import INCOME, EXPENSE
from services import (FinanceService, ValidationError, parse_amount,
                      parse_date, format_money, month_range)


class ParseTests(unittest.TestCase):
    def test_amount_valid(self):
        self.assertEqual(parse_amount("100"), 10000)
        self.assertEqual(parse_amount("1 250,50"), 125050)
        self.assertEqual(parse_amount("0.01"), 1)

    def test_amount_invalid(self):
        for bad in ["", None, "abc", "-5", "0", "10.999", "nan", "99999999999"]:
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    parse_amount(bad)

    def test_date(self):
        self.assertEqual(parse_date("05.03.2026"), date(2026, 3, 5))
        for bad in ["31.02.2026", "2026-03-05", "", "abc"]:
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    parse_date(bad)

    def test_format_money(self):
        self.assertEqual(format_money(125050), "1 250,50 ₽")
        self.assertEqual(format_money(5), "0,05 ₽")
        self.assertEqual(format_money(-100000), "-1 000,00 ₽")

    def test_month_range(self):
        self.assertEqual(month_range(2026, 12), (date(2026, 12, 1), date(2026, 12, 31)))
        self.assertEqual(month_range(2028, 2)[1], date(2028, 2, 29))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.svc = FinanceService(self.db)
        self.inc = self.svc.categories(INCOME)[0].id
        self.exp = self.svc.categories(EXPENSE)[0].id
        self.exp2 = self.svc.categories(EXPENSE)[1].id

    def tearDown(self):
        self.db.close()

    def test_default_categories(self):
        self.assertGreaterEqual(len(self.svc.categories(INCOME)), 3)
        self.assertGreaterEqual(len(self.svc.categories(EXPENSE)), 5)

    def test_balance(self):
        self.svc.add_operation(INCOME, "50000", self.inc, "", "01.03.2026")
        self.svc.add_operation(EXPENSE, "1200,50", self.exp, "обед", "02.03.2026")
        self.assertEqual(self.svc.balance(), 5000000 - 120050)

    def test_kind_mismatch(self):
        with self.assertRaises(ValidationError):
            self.svc.add_operation(INCOME, "100", self.exp, "", "01.03.2026")

    def test_bad_category(self):
        for bad in [None, "x", 99999]:
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    self.svc.add_operation(EXPENSE, "100", bad, "", "01.03.2026")

    def test_long_note(self):
        with self.assertRaises(ValidationError):
            self.svc.add_operation(EXPENSE, "100", self.exp, "я" * 101, "01.03.2026")

    def test_month_summary_filters_by_month(self):
        self.svc.add_operation(INCOME, "1000", self.inc, "", "10.03.2026")
        self.svc.add_operation(EXPENSE, "300", self.exp, "", "11.03.2026")
        self.svc.add_operation(EXPENSE, "700", self.exp, "", "01.04.2026")
        s = self.svc.month_summary(2026, 3)
        self.assertEqual((s["income"], s["expense"], s["balance"]),
                         (100000, 30000, 70000))

    def test_expense_by_category(self):
        self.svc.add_operation(EXPENSE, "300", self.exp, "", "05.03.2026")
        self.svc.add_operation(EXPENSE, "100", self.exp2, "", "06.03.2026")
        rows = self.svc.expense_by_category(2026, 3)
        self.assertEqual(len(rows), 2)
        self.assertGreaterEqual(rows[0][1], rows[1][1])
        self.assertAlmostEqual(sum(r[2] for r in rows), 1.0)
        self.assertAlmostEqual(rows[0][2], 0.75)

    def test_empty_month(self):
        self.assertEqual(self.svc.expense_by_category(2030, 1), [])
        self.assertEqual(self.svc.month_summary(2030, 1)["balance"], 0)

    def test_budget_status(self):
        self.svc.set_limit(self.exp, "500")
        self.svc.add_operation(EXPENSE, "600", self.exp, "", "05.03.2026")
        st = {s.category_id: s for s in self.svc.budget_statuses(2026, 3)}
        self.assertTrue(st[self.exp].exceeded)
        self.assertAlmostEqual(st[self.exp].ratio, 1.2)
        self.assertFalse(st[self.exp2].exceeded)
        self.assertEqual(st[self.exp2].limit_kop, 0)

    def test_budget_reset(self):
        self.svc.set_limit(self.exp, "500")
        self.svc.set_limit(self.exp, "")
        st = {s.category_id: s for s in self.svc.budget_statuses(2026, 3)}
        self.assertEqual(st[self.exp].limit_kop, 0)

    def test_delete(self):
        tx_id = self.svc.add_operation(EXPENSE, "100", self.exp, "", "05.03.2026")
        self.assertTrue(self.svc.delete_operation(tx_id))
        self.assertFalse(self.svc.delete_operation(tx_id))
        self.assertEqual(self.svc.balance(), 0)

    def test_recent_order(self):
        self.svc.add_operation(EXPENSE, "1", self.exp, "a", "01.03.2026")
        self.svc.add_operation(EXPENSE, "2", self.exp, "b", "03.03.2026")
        self.svc.add_operation(EXPENSE, "3", self.exp, "c", "02.03.2026")
        notes = [t.note for t in self.svc.recent(2)]
        self.assertEqual(notes, ["b", "c"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
