"""One test per disagreement type, each built from a real row in the CSVs
(not an invented fixture) - see the file comments for exactly which one.

These build SourceRecord/SourceEntry objects in memory without saving
them, so they don't touch the database at all - this is testing the part
the brief calls out specifically: "the part where the disagreements are
decided."
"""

from decimal import Decimal

from django.test import SimpleTestCase

from reconcile.models import Location, SourceEntry, SourceRecord
from reconcile.services.compare import (
    DUPLICATE_IN_B,
    LOCATION_MISMATCH,
    MISSING_IN_B,
    ORPHAN_IN_B,
    VALUE_MISMATCH,
    find_disagreements,
    find_disagreements_for_org,
)

LOCATIONS = [
    Location(location_id="LOC-101", org_id="ORG-A"),
    Location(location_id="LOC-102", org_id="ORG-A"),
    Location(location_id="LOC-103", org_id="ORG-A"),
    Location(location_id="LOC-201", org_id="ORG-B"),
    Location(location_id="LOC-202", org_id="ORG-B"),
]


def record(record_id, location_id, total_value, state="CONFIRMED"):
    return SourceRecord(
        record_id=record_id,
        location_id=location_id,
        total_value=Decimal(total_value) if total_value is not None else None,
        state=state,
    )


def entry(entry_id, record_ref_normalized, location_id, value, value_raw=""):
    return SourceEntry(
        entry_id=entry_id,
        record_ref_normalized=record_ref_normalized,
        location_id=location_id,
        value=value,
        value_raw=value_raw,
    )


class MissingInBTests(SimpleTestCase):
    def test_record_with_no_b_entry_is_flagged(self):
        # REC-1015: real record in system_a.csv, no matching row anywhere in system_b.csv
        records = [record("REC-1015", "LOC-103", "41095.33")]
        ds = find_disagreements(records, [], LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, MISSING_IN_B)
        self.assertEqual(ds[0].record_id, "REC-1015")
        self.assertEqual(ds[0].org_id, "ORG-A")


class OrphanInBTests(SimpleTestCase):
    def test_entry_pointing_at_nonexistent_record_is_flagged(self):
        # system_b.csv entry ENT/2026/4901 references REC-1999, which doesn't exist in system_a.csv
        entries = [entry("ENT/2026/4901", "REC-1999", "LOC-102", Decimal("41250.00"))]
        ds = find_disagreements([], entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, ORPHAN_IN_B)
        self.assertEqual(ds[0].record_id, "REC-1999")
        # no System A record to anchor identity to at all, so we fall back to B's own location
        self.assertEqual(ds[0].org_id, "ORG-A")


class DuplicateInBTests(SimpleTestCase):
    def test_same_record_entered_twice_is_flagged(self):
        # REC-1042: entries ENT/2026/4042 and ENT/2026/4902, identical value - a true duplicate
        records = [record("REC-1042", "LOC-101", "112837.06")]
        entries = [
            entry("ENT/2026/4042", "REC-1042", "LOC-101", Decimal("112837.06")),
            entry("ENT/2026/4902", "REC-1042", "LOC-101", Decimal("112837.06")),
        ]
        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, DUPLICATE_IN_B)

    def test_split_entries_that_sum_correctly_are_still_flagged(self):
        # REC-1055: entries ENT/2026/4055 (71950.93) + ENT/2026/4903 (107926.39) sum to
        # A's total (179877.32) exactly - could be a legitimate multi-part entry rather
        # than a copy-paste error, but we flag it the same as a plain duplicate instead
        # of guessing intent (see DECISIONS.md)
        records = [record("REC-1055", "LOC-103", "179877.32")]
        entries = [
            entry("ENT/2026/4055", "REC-1055", "LOC-103", Decimal("71950.93")),
            entry("ENT/2026/4903", "REC-1055", "LOC-103", Decimal("107926.39")),
        ]
        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, DUPLICATE_IN_B)


class ValueMismatchTests(SimpleTestCase):
    def test_different_values_are_flagged(self):
        # REC-1064: system_b.csv's value is the quoted, comma-formatted string
        # "1,25,400.00" (parses to 125400.00), genuinely different from A's 183244.16 -
        # this also proves the comma format is parsed, not just string-diffed
        records = [record("REC-1064", "LOC-101", "183244.16")]
        entries = [entry("ENT/2026/4064", "REC-1064", "LOC-101", Decimal("125400.00"), "1,25,400.00")]
        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, VALUE_MISMATCH)
        self.assertEqual(ds[0].b_value, "125400.00")

    def test_blank_b_value_counts_as_a_mismatch(self):
        # REC-1050: system_b.csv's value column is empty for this entry
        records = [record("REC-1050", "LOC-202", "160405.85")]
        entries = [entry("ENT/2026/4050", "REC-1050", "LOC-202", None, "")]
        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, VALUE_MISMATCH)
        self.assertEqual(ds[0].b_value, "blank")


class LocationMismatchTests(SimpleTestCase):
    def test_tenant_boundary_case_is_flagged_and_scoped_to_org_a_only(self):
        # REC-1077: System A files it under LOC-102 (ORG-A), System B under LOC-201
        # (ORG-B) - same value both sides, only the tenant disagrees. This is the
        # concrete "do not leak across the boundary" case from the brief: it must
        # show up under ORG-A (A owns the record_id) and never under ORG-B.
        records = [record("REC-1077", "LOC-102", "83361.40")]
        entries = [entry("ENT/2026/4077", "REC-1077", "LOC-201", Decimal("83361.40"))]

        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].reason, LOCATION_MISMATCH)
        self.assertEqual(ds[0].org_id, "ORG-A")

        org_a = find_disagreements_for_org(records, entries, LOCATIONS, "ORG-A")
        org_b = find_disagreements_for_org(records, entries, LOCATIONS, "ORG-B")
        self.assertEqual(len(org_a), 1)
        self.assertEqual(len(org_b), 0)


class NonErrorTests(SimpleTestCase):
    def test_voided_record_with_matching_value_is_not_flagged(self):
        # REC-1019 is VOIDED in system_a.csv, but System B still has a matching entry
        # with the same value - state isn't part of what we compare, so this is
        # correctly treated as a non-error, not a disagreement
        records = [record("REC-1019", "LOC-202", "57092.35", state="VOIDED")]
        entries = [entry("ENT/2026/4019", "REC-1019", "LOC-202", Decimal("57092.35"))]
        ds = find_disagreements(records, entries, LOCATIONS)
        self.assertEqual(ds, [])
