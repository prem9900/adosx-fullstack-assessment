"""Small, boring parsers for the dirty bits of the CSVs.

Every function here returns None (or '') on anything it can't parse instead
of raising, so a bad row never crashes the import. The original text is
always kept elsewhere (raw_row) so nothing is lost, just left unparsed.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# matches the digits inside a record ref no matter how it's dressed up:
# "REC-1034", "rec1034", " REC - 1070 ", "1112" all reduce to the same number
_REF_DIGITS = re.compile(r"(\d+)")


def normalize_record_ref(raw: str) -> str:
    """Best-effort clean-up of a System B record_ref back to REC-#### form."""
    if not raw:
        return ""
    match = _REF_DIGITS.search(raw)
    if not match:
        return ""
    return f"REC-{match.group(1)}"


def parse_decimal(raw: str) -> Decimal | None:
    """Parse a money value, tolerating thousand separators like '1,25,400.00'."""
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(raw: str) -> date | None:
    """Every date we've seen is ISO (YYYY-MM-DD); anything else comes back None."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
