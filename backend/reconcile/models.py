from django.db import models


class Location(models.Model):
    """The only place the location -> org (tenant) mapping exists."""

    location_id = models.CharField(max_length=32, primary_key=True)
    org_id = models.CharField(max_length=32)
    location_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.location_id


class SourceRecord(models.Model):
    """One row per event, exactly as System A recorded it. record_id is the identifier."""

    record_id = models.CharField(max_length=32, primary_key=True)

    # kept as plain text, not a hard FK, so an unknown location can never block an import
    location_id = models.CharField(max_length=64, blank=True)

    event_date = models.DateField(null=True, blank=True)
    event_date_raw = models.CharField(max_length=32, blank=True)

    category_code = models.CharField(max_length=32, blank=True)
    actor_id = models.CharField(max_length=32, blank=True)

    base_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_value_raw = models.CharField(max_length=64, blank=True)

    state = models.CharField(max_length=32, blank=True)

    # the untouched original row, so nothing is ever truly lost even if parsing failed
    raw_row = models.JSONField(default=dict)

    def __str__(self):
        return self.record_id


class SourceEntry(models.Model):
    """One row per entry, as System B recorded it. May be more than one per record_ref."""

    entry_id = models.CharField(max_length=32, primary_key=True)

    record_ref_raw = models.CharField(max_length=64, blank=True)
    # best-effort cleaned up form (REC-####); blank if we couldn't make sense of it at all
    record_ref_normalized = models.CharField(max_length=32, blank=True, db_index=True)

    location_id = models.CharField(max_length=64, blank=True)

    recorded_on = models.DateField(null=True, blank=True)
    recorded_on_raw = models.CharField(max_length=32, blank=True)

    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    value_raw = models.CharField(max_length=64, blank=True)

    label = models.CharField(max_length=255, blank=True)

    raw_row = models.JSONField(default=dict)

    def __str__(self):
        return self.entry_id
