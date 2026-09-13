"""Entity parsing for dates, times and patient identifiers.

`parse_datetime` keeps its original contract: it returns a naive datetime only
when a concrete calendar date is known. It never invents a clock time for a
bare relative expression such as "kal" - the agent asks for the time instead.
"""

import re
from datetime import date, datetime

from .dates import parse_clock_time, resolve_relative_date

_ISO_DATE_TIME = re.compile(r"(20\d{2}-\d{2}-\d{2})[ T](\d{1,2}:\d{2})")
_ISO_DATE = re.compile(r"(20\d{2}-\d{2}-\d{2})")

# Patient identifiers are strictly formatted. A bare number such as "11222" is
# never treated as a patient ID: the clinic's own IDs are P-### / PATIENT-###,
# and guessing here would send an unverified ID into the booking transaction.
_PATIENT_ID = re.compile(r"\b(?:PATIENT|P)-(\d{1,10})\b", re.I)


def parse_date(text: str, now: datetime | None = None) -> date | None:
    """Return an explicit ISO date or a resolved relative date."""
    match = _ISO_DATE.search(text or "")
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            pass

    resolved = resolve_relative_date(text or "", now)
    return resolved.date if resolved else None


def parse_datetime(text: str, now: datetime | None = None) -> datetime | None:
    """Resolve a message to a naive datetime, or None when the date is unknown."""
    text = text or ""

    # 1. Fully explicit "2026-09-14 11:00".
    match = _ISO_DATE_TIME.search(text)
    if match:
        try:
            return datetime.fromisoformat(f"{match.group(1)} {match.group(2)}")
        except ValueError:
            pass

    clock = parse_clock_time(text)

    # 2. Explicit ISO date with the time written separately,
    #    e.g. "on 2026-09-16 at 10:00".
    iso = _ISO_DATE.search(text)
    if iso:
        try:
            day = date.fromisoformat(iso.group(1))
        except ValueError:
            return None
        if clock:
            return datetime(day.year, day.month, day.day, clock[0], clock[1])
        # Date-only request: midnight is a search-window start, not a promise.
        # The agent still requires a database slot before booking.
        return datetime(day.year, day.month, day.day)

    # 3. Relative date plus an explicit clock time, e.g. "kal 2:30 pm".
    resolved = resolve_relative_date(text, now)
    if resolved and clock:
        return datetime(
            resolved.date.year,
            resolved.date.month,
            resolved.date.day,
            clock[0],
            clock[1],
        )

    # A relative date with no time is deliberately not a datetime.
    return None


def parse_patient_id(text: str) -> str | None:
    """Extract a well-formed patient ID, normalised to P-### form."""
    match = _PATIENT_ID.search(text or "")
    if not match:
        return None
    return f"P-{match.group(1)}"


def looks_like_bare_id_attempt(text: str) -> bool:
    """True when the user supplied a bare number where an ID was expected."""
    stripped = (text or "").strip().strip(".,!?")
    return bool(re.fullmatch(r"\d{3,12}", stripped))
