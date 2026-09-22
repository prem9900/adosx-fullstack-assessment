"""Runs the real importer against the real committed CSVs (backend/data/) -
proves the numbers in the plan are actually true, not just eyeballed.
"""

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from reconcile.models import Location, SourceEntry, SourceRecord


class ImportDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_data", data_dir=str(settings.DATA_DIR))

    def test_row_counts_match_the_csvs_exactly(self):
        self.assertEqual(Location.objects.count(), 5)
        self.assertEqual(SourceRecord.objects.count(), 120)
        # system_b.csv has 121 rows, not 120 - the brief says "120 on each side",
        # but the file itself has one extra (see DECISIONS.md)
        self.assertEqual(SourceEntry.objects.count(), 121)

    def test_blank_fields_are_kept_not_dropped(self):
        # REC-1050 has a blank actor_id in system_a.csv - row must still be there
        record = SourceRecord.objects.get(record_id="REC-1050")
        self.assertEqual(record.actor_id, "")

        # its system_b.csv entry has a blank value - must still be there too
        entry = SourceEntry.objects.get(record_ref_normalized="REC-1050")
        self.assertIsNone(entry.value)
        self.assertEqual(entry.value_raw, "")

    def test_malformed_record_ref_is_normalized(self):
        entry = SourceEntry.objects.get(record_ref_raw="rec1034")
        self.assertEqual(entry.record_ref_normalized, "REC-1034")

    def test_comma_formatted_value_is_parsed_correctly(self):
        entry = SourceEntry.objects.get(record_ref_normalized="REC-1064")
        self.assertEqual(str(entry.value), "125400.00")

    def test_location_mismatch_survives_import_intact(self):
        # REC-1077: system_a.csv says LOC-102, system_b.csv says LOC-201 for the same
        # record - the importer must not "fix" this, just store both as given
        record = SourceRecord.objects.get(record_id="REC-1077")
        entry = SourceEntry.objects.get(record_ref_normalized="REC-1077")
        self.assertEqual(record.location_id, "LOC-102")
        self.assertEqual(entry.location_id, "LOC-201")
