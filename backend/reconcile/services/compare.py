"""Match System A records to System B entries and report where they disagree.

Neither system is authoritative on values or on location - every
disagreement shows both sides, never a single "correct" answer. System
A's location is used only to decide which tenant a row is filed under
(an identity/access-control call, since B's record_ref is itself defined
as pointing back at A's id space) - never as a claim that A's numbers
are more trustworthy than B's.
"""

from dataclasses import dataclass
from decimal import Decimal

MISSING_IN_B = "MISSING_IN_B"
ORPHAN_IN_B = "ORPHAN_IN_B"
DUPLICATE_IN_B = "DUPLICATE_IN_B"
VALUE_MISMATCH = "VALUE_MISMATCH"
LOCATION_MISMATCH = "LOCATION_MISMATCH"

REASONS = [MISSING_IN_B, ORPHAN_IN_B, DUPLICATE_IN_B, VALUE_MISMATCH, LOCATION_MISMATCH]

# a cent or two of rounding noise shouldn't count as a real disagreement
_VALUE_TOLERANCE = Decimal("0.01")


@dataclass
class Disagreement:
    reason: str
    record_id: str
    org_id: str | None
    location_id: str | None
    a_value: str
    b_value: str
    detail: str


def _fmt(value):
    return "" if value is None else str(value)


def _fmt_b_value(entry):
    if entry.value is not None:
        return _fmt(entry.value)
    return "blank" if not entry.value_raw else f"unparseable: {entry.value_raw!r}"


def find_disagreements(records, entries, locations):
    """
    records: iterable of SourceRecord (system A)
    entries: iterable of SourceEntry (system B)
    locations: iterable of Location, used to resolve org_id from location_id

    Returns every disagreement across both tenants - callers that need a
    single tenant's view must filter by org_id themselves (see
    find_disagreements_for_org), the boundary is never assumed here.
    """
    org_by_location = {loc.location_id: loc.org_id for loc in locations}

    entries_by_ref = {}
    for entry in entries:
        entries_by_ref.setdefault(entry.record_ref_normalized, []).append(entry)

    records_by_id = {record.record_id: record for record in records}

    disagreements = []

    for record in records:
        org_id = org_by_location.get(record.location_id)
        matches = entries_by_ref.get(record.record_id, [])

        if len(matches) == 0:
            disagreements.append(Disagreement(
                reason=MISSING_IN_B,
                record_id=record.record_id,
                org_id=org_id,
                location_id=record.location_id,
                a_value=_fmt(record.total_value),
                b_value="",
                detail="System A has this record; System B has no matching entry.",
            ))
            continue

        if len(matches) > 1:
            # more than one B entry claims this record - we flag it as-is rather than
            # guessing whether it's a copy-paste duplicate or a legitimate multi-part
            # split (e.g. two entries whose values happen to sum to A's total)
            parts = ", ".join(f"{e.entry_id}={_fmt_b_value(e)}" for e in matches)
            disagreements.append(Disagreement(
                reason=DUPLICATE_IN_B,
                record_id=record.record_id,
                org_id=org_id,
                location_id=record.location_id,
                a_value=_fmt(record.total_value),
                b_value=parts,
                detail=f"System B has {len(matches)} entries for this record: {parts}.",
            ))
            continue

        entry = matches[0]

        values_differ = (
            entry.value is None
            or record.total_value is None
            or abs(entry.value - record.total_value) > _VALUE_TOLERANCE
        )
        if values_differ:
            disagreements.append(Disagreement(
                reason=VALUE_MISMATCH,
                record_id=record.record_id,
                org_id=org_id,
                location_id=record.location_id,
                a_value=_fmt(record.total_value),
                b_value=_fmt_b_value(entry),
                detail="System A and System B report different values for this record.",
            ))

        if entry.location_id and entry.location_id != record.location_id:
            disagreements.append(Disagreement(
                reason=LOCATION_MISMATCH,
                record_id=record.record_id,
                org_id=org_id,
                location_id=record.location_id,
                a_value=record.location_id,
                b_value=entry.location_id,
                detail=(
                    f"System A files this under {record.location_id}; "
                    f"System B files the same record under {entry.location_id} instead."
                ),
            ))

    # entries whose normalized ref doesn't match any real System A record
    for ref, matches in entries_by_ref.items():
        if ref and ref in records_by_id:
            continue
        for entry in matches:
            org_id = org_by_location.get(entry.location_id)
            disagreements.append(Disagreement(
                reason=ORPHAN_IN_B,
                record_id=ref or entry.record_ref_raw or entry.entry_id,
                org_id=org_id,
                location_id=entry.location_id,
                a_value="",
                b_value=_fmt_b_value(entry),
                detail=(
                    f"System B entry {entry.entry_id} references "
                    f"{entry.record_ref_raw!r}, which does not exist in System A."
                ),
            ))

    return disagreements


def find_disagreements_for_org(records, entries, locations, org_id):
    """The only entry point the API uses - never returns a row for another tenant."""
    return [d for d in find_disagreements(records, entries, locations) if d.org_id == org_id]
