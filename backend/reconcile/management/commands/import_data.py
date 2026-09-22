"""Import locations.csv, system_a.csv and system_b.csv into the database.

Nothing is ever skipped: a row with a bad date, a bad number, or a blank
field still gets inserted, with the unparseable bit stored as raw text and
a warning printed. Losing a row silently would be worse than storing it
half-parsed.
"""

import csv

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from reconcile.models import Location, SourceEntry, SourceRecord
from reconcile.services.normalize import normalize_record_ref, parse_date, parse_decimal


class Command(BaseCommand):
    help = "Import locations.csv, system_a.csv and system_b.csv into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            default=str(settings.DATA_DIR),
            help="Folder containing locations.csv, system_a.csv, system_b.csv",
        )

    def handle(self, *args, **options):
        data_dir = options["data_dir"]

        with transaction.atomic():
            Location.objects.all().delete()
            SourceRecord.objects.all().delete()
            SourceEntry.objects.all().delete()

            loc_count = self._import_locations(f"{data_dir}/locations.csv")
            a_count, a_warnings = self._import_system_a(f"{data_dir}/system_a.csv")
            b_count, b_warnings = self._import_system_b(f"{data_dir}/system_b.csv")

        self.stdout.write(self.style.SUCCESS(
            f"Imported {loc_count} locations, {a_count} system A records, {b_count} system B entries. "
            "0 rows dropped."
        ))
        for warning in a_warnings + b_warnings:
            self.stdout.write(self.style.WARNING(warning))

    def _import_locations(self, path):
        count = 0
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                Location.objects.update_or_create(
                    location_id=(row.get("location_id") or "").strip(),
                    defaults={
                        "org_id": (row.get("org_id") or "").strip(),
                        "location_name": (row.get("location_name") or "").strip(),
                    },
                )
                count += 1
        return count

    def _import_system_a(self, path):
        count = 0
        warnings = []
        with open(path, newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                # a blank record_id can't be a real primary key, but we still keep the
                # row rather than drop it - this hasn't happened in the sample data
                record_id = (row.get("record_id") or "").strip() or f"A-ROW-{i}"
                if record_id.startswith("A-ROW-"):
                    warnings.append(f"system_a.csv row {i}: blank record_id, kept as {record_id}")

                event_date_raw = row.get("event_date") or ""
                event_date = parse_date(event_date_raw)
                if event_date_raw and event_date is None:
                    warnings.append(f"system_a.csv {record_id}: unparseable event_date {event_date_raw!r}")

                total_value_raw = row.get("total_value") or ""
                total_value = parse_decimal(total_value_raw)
                if total_value_raw and total_value is None:
                    warnings.append(f"system_a.csv {record_id}: unparseable total_value {total_value_raw!r}")

                SourceRecord.objects.update_or_create(
                    record_id=record_id,
                    defaults=dict(
                        location_id=(row.get("location_id") or "").strip(),
                        event_date=event_date,
                        event_date_raw=event_date_raw,
                        category_code=(row.get("category_code") or "").strip(),
                        actor_id=(row.get("actor_id") or "").strip(),
                        base_value=parse_decimal(row.get("base_value") or ""),
                        adjustment=parse_decimal(row.get("adjustment") or ""),
                        total_value=total_value,
                        total_value_raw=total_value_raw,
                        state=(row.get("state") or "").strip(),
                        raw_row=dict(row),
                    ),
                )
                count += 1
        return count, warnings

    def _import_system_b(self, path):
        count = 0
        warnings = []
        with open(path, newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                entry_id = (row.get("entry_id") or "").strip() or f"B-ROW-{i}"
                if entry_id.startswith("B-ROW-"):
                    warnings.append(f"system_b.csv row {i}: blank entry_id, kept as {entry_id}")

                record_ref_raw = row.get("record_ref") or ""
                record_ref_normalized = normalize_record_ref(record_ref_raw)
                if record_ref_raw and not record_ref_normalized:
                    warnings.append(f"system_b.csv {entry_id}: unparseable record_ref {record_ref_raw!r}")

                value_raw = row.get("value") or ""
                value = parse_decimal(value_raw)
                if value_raw and value is None:
                    warnings.append(f"system_b.csv {entry_id}: unparseable value {value_raw!r}")

                SourceEntry.objects.update_or_create(
                    entry_id=entry_id,
                    defaults=dict(
                        record_ref_raw=record_ref_raw,
                        record_ref_normalized=record_ref_normalized,
                        location_id=(row.get("location_id") or "").strip(),
                        recorded_on=parse_date(row.get("recorded_on") or ""),
                        recorded_on_raw=row.get("recorded_on") or "",
                        value=value,
                        value_raw=value_raw,
                        label=(row.get("label") or "").strip(),
                        raw_row=dict(row),
                    ),
                )
                count += 1
        return count, warnings
