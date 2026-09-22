"""Each case here is a real dirty value copied straight out of system_b.csv."""

from decimal import Decimal

from django.test import SimpleTestCase

from reconcile.services.normalize import normalize_record_ref, parse_date, parse_decimal


class NormalizeRecordRefTests(SimpleTestCase):
    def test_clean_ref_unchanged(self):
        self.assertEqual(normalize_record_ref("REC-1001"), "REC-1001")

    def test_lowercase_no_dash(self):
        # system_b.csv entry ENT/2026/4034
        self.assertEqual(normalize_record_ref("rec1034"), "REC-1034")

    def test_padded_with_spaces(self):
        # system_b.csv entry ENT/2026/4070
        self.assertEqual(normalize_record_ref(" REC - 1070 "), "REC-1070")

    def test_bare_digits(self):
        # system_b.csv entry ENT/2026/4112
        self.assertEqual(normalize_record_ref("1112"), "REC-1112")

    def test_blank_returns_empty_string(self):
        self.assertEqual(normalize_record_ref(""), "")


class ParseDecimalTests(SimpleTestCase):
    def test_plain_value(self):
        self.assertEqual(parse_decimal("88969.92"), Decimal("88969.92"))

    def test_indian_style_thousand_separators(self):
        # system_b.csv entry ENT/2026/4064, quoted "1,25,400.00"
        self.assertEqual(parse_decimal("1,25,400.00"), Decimal("125400.00"))

    def test_blank_is_none_not_zero(self):
        self.assertIsNone(parse_decimal(""))

    def test_garbage_is_none(self):
        self.assertIsNone(parse_decimal("garbage"))


class ParseDateTests(SimpleTestCase):
    def test_iso_date(self):
        self.assertEqual(str(parse_date("2026-04-03")), "2026-04-03")

    def test_unparseable_is_none(self):
        self.assertIsNone(parse_date("not-a-date"))
