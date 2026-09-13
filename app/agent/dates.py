"""Deterministic relative-date resolution for the clinic assistant.

Dates are resolved with Python date arithmetic in the clinic's own timezone
(Asia/Karachi), never inferred by a language model. A receptionist that
guesses "tomorrow" wrongly books the wrong day, so this module is the single
authority for turning a relative expression into a concrete calendar date.

The resolver deliberately does NOT recognise bare weekday names ("Saturday",
"اتوار"). Those are already answered correctly from the knowledge base and
treating them as relative dates would rewrite queries that work today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("Asia/Karachi")


def now_clinic(now: datetime | None = None) -> datetime:
    """Current time in the clinic timezone."""
    if now is not None:
        return now
    return datetime.now(CLINIC_TZ)


def today_clinic(now: datetime | None = None) -> date:
    return now_clinic(now).date()


# --------------------------------------------------------------------------
# Weekday vocabulary (English / Urdu / Roman Urdu).
# Used only for "next <weekday>" / "this <weekday>" style expressions.
# --------------------------------------------------------------------------

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

WEEKDAY_LOOKUP: dict[str, int] = {}

for _index, _name in enumerate(WEEKDAY_NAMES):
    WEEKDAY_LOOKUP[_name.lower()] = _index

WEEKDAY_LOOKUP.update(
    {
        # Urdu script
        "پیر": 0,
        "سوموار": 0,
        "منگل": 1,
        "بدھ": 2,
        "جمعرات": 3,
        "جمعہ": 4,
        "ہفتہ": 5,
        "سنیچر": 5,
        "اتوار": 6,
        # Roman Urdu
        "peer": 0,
        "somwar": 0,
        "mangal": 1,
        "budh": 2,
        "jumerat": 3,
        "jumeraat": 3,
        "juma": 4,
        "jumma": 4,
        "hafta": 5,
        "haftay": 5,
        "sanichar": 5,
        "itwar": 6,
        "aitwar": 6,
        "itvar": 6,
    }
)


# --------------------------------------------------------------------------
# Tense cues.
#
# Urdu/Roman-Urdu "kal" (کل) and "parson" (پرسوں) are symmetric: they mean
# both the day before and the day after today. Written Urdu resolves this
# from verb tense, so we look for explicit past-tense markers and otherwise
# default forward — a receptionist question is almost always about an
# upcoming visit.
#
# Deliberately excludes common English words such as "the" and "were not"
# fragments that would misfire on ordinary sentences.
# --------------------------------------------------------------------------

PAST_TENSE = re.compile(
    r"\b(?:tha|thi|thay|thi\?|gaya|gayi|gaye|hua|huwa|hui|huye|"
    r"kiya\s+tha|gujra|guzra|guzishta|pichla|pichlay|pichle|"
    r"was|were|had|yesterday|closed\s+on)\b"
    r"|تھا|تھی|تھے|گیا|گئی|گئے|گزشتہ|پچھلے|پچھلا",
    re.I,
)


@dataclass(frozen=True)
class ResolvedDate:
    """A relative expression resolved to a concrete date."""

    date: date
    weekday: str
    expression: str
    offset_days: int

    @property
    def iso(self) -> str:
        return self.date.isoformat()


# --------------------------------------------------------------------------
# Relative expressions.
#
# Ordered longest-first so that "aglay din" wins over "din" and
# "day after tomorrow" wins over "tomorrow".
# --------------------------------------------------------------------------

_FIXED_OFFSETS: list[tuple[str, int]] = [
    # day after tomorrow
    (r"day\s+after\s+tomorrow", 2),
    (r"parson\s+ke\s+baad", 3),
    # day before yesterday
    (r"day\s+before\s+yesterday", -2),
    # tomorrow
    (r"tomorrow", 1),
    (r"aglay\s+din", 1),
    (r"agle\s+din", 1),
    (r"agli\s+subah", 1),
    (r"next\s+day", 1),
    (r"اگلے\s+دن", 1),
    (r"اگلا\s+دن", 1),
    # today
    (r"today", 0),
    (r"aaj", 0),
    (r"aj", 0),
    (r"آج", 0),
    # yesterday
    (r"yesterday", -1),
    (r"guzra\s+kal", -1),
    (r"guzishta\s+kal", -1),
    (r"گزشتہ\s+کل", -1),
]

# Ambiguous, tense-sensitive expressions: (pattern, forward, backward).
_AMBIGUOUS: list[tuple[str, int, int]] = [
    (r"parson", 2, -2),
    (r"پرسوں", 2, -2),
    (r"kal", 1, -1),
    (r"کل", 1, -1),
]

# Urdu "hafta" means both "week" and "Saturday". Qualified by next/aglay it is
# almost always "next week", so this is checked before the weekday lookup -
# otherwise "aglay hafta" silently resolves to the coming Saturday.
_NEXT_WEEK = re.compile(
    r"\b(?:next|coming|aglay|agle|agla)\s+(?:week|hafta|hafte|haftay)\b"
    r"|اگلے\s*ہفتے",
    re.I,
)

_NEXT_WEEKDAY = re.compile(
    r"\b(next|this|coming|aglay|agle|agla)\s+"
    r"([A-Za-z\u0600-\u06FF]+)",
    re.I,
)


def resolve_relative_date(
    text: str,
    now: datetime | None = None,
) -> ResolvedDate | None:
    """Resolve the first relative-date expression in *text*.

    Returns None when the text contains no relative expression, so callers can
    leave ordinary queries completely untouched.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    today = today_clinic(now)
    lowered = text.lower()

    # 1. "next week" before weekday matching, so "hafta" is not read as Saturday.
    match = _NEXT_WEEK.search(text)
    if match:
        resolved = today + timedelta(days=7)
        return ResolvedDate(resolved, WEEKDAY_NAMES[resolved.weekday()], match.group(0), 7)

    # 2. "next Monday" / "aglay itwar" — an explicit weekday target.
    match = _NEXT_WEEKDAY.search(text)
    if match:
        qualifier = match.group(1).lower()
        candidate = match.group(2).lower().strip("،,.?؟!")
        target = WEEKDAY_LOOKUP.get(candidate)
        if target is not None:
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            if qualifier in {"next", "aglay", "agle", "agla"} and delta < 1:
                delta += 7
            resolved = today + timedelta(days=delta)
            return ResolvedDate(
                resolved,
                WEEKDAY_NAMES[resolved.weekday()],
                match.group(0),
                delta,
            )

    # 3. Unambiguous fixed offsets.
    for pattern, offset in _FIXED_OFFSETS:
        found = re.search(rf"(?<![\w\u0600-\u06FF]){pattern}(?![\w\u0600-\u06FF])", text, re.I)
        if found:
            resolved = today + timedelta(days=offset)
            return ResolvedDate(
                resolved,
                WEEKDAY_NAMES[resolved.weekday()],
                found.group(0),
                offset,
            )

    # 4. Tense-sensitive expressions.
    backward = bool(PAST_TENSE.search(lowered))
    for pattern, forward_offset, backward_offset in _AMBIGUOUS:
        found = re.search(rf"(?<![\w\u0600-\u06FF]){pattern}(?![\w\u0600-\u06FF])", text, re.I)
        if found:
            offset = backward_offset if backward else forward_offset
            resolved = today + timedelta(days=offset)
            return ResolvedDate(
                resolved,
                WEEKDAY_NAMES[resolved.weekday()],
                found.group(0),
                offset,
            )

    return None


# --------------------------------------------------------------------------
# Clock-time parsing.
# --------------------------------------------------------------------------

_TIME_PATTERNS = [
    # 2:30 pm / 14:30 / 2 pm
    re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", re.I),
    re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.I),
]

# A bare hour is only read as a time when the sentence marks it as one
# ("10 baje", "subah 10"). Without such a marker a stray number stays a
# number, so "schedule_id=75" never becomes 07:05.
_BARE_HOUR = re.compile(r"\b(\d{1,2})\b\s*(?:baje|bajay|bje|بجے)?", re.I)

_CLOCK_MARKER = re.compile(r"\b(?:baje|bajay|bje)\b|بجے", re.I)

# Roman Urdu / Urdu parts of day, used only to disambiguate a bare hour.
_MERIDIEM_HINTS = [
    (re.compile(r"\b(subah|subh|sawere|صبح)\b", re.I), "am"),
    (re.compile(r"\b(dopahar|dopeher|دوپہر)\b", re.I), "pm"),
    (re.compile(r"\b(shaam|sham|شام)\b", re.I), "pm"),
    (re.compile(r"\b(raat|رات)\b", re.I), "pm"),
]


def parse_clock_time(text: str) -> tuple[int, int] | None:
    """Return (hour, minute) in 24-hour form, or None."""
    if not isinstance(text, str):
        return None

    hint = None
    for pattern, meridiem in _MERIDIEM_HINTS:
        if pattern.search(text):
            hint = meridiem
            break

    patterns = list(_TIME_PATTERNS)
    if hint or _CLOCK_MARKER.search(text):
        patterns.append(_BARE_HOUR)

    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue

        if pattern is _BARE_HOUR:
            hour = int(match.group(1))
            if not 0 <= hour <= 23:
                continue
            if hint == "am" and hour == 12:
                hour = 0
            elif hint == "pm" and hour < 12:
                hour += 12
            elif hint is None and 1 <= hour <= 7:
                # "5 baje" at a clinic open 09:00-19:00 means the afternoon.
                hour += 12
            return hour, 0

        groups = match.groups()
        hour = int(groups[0])
        if len(groups) == 3:
            minute = int(groups[1] or 0)
            meridiem = (groups[2] or "").lower()
        else:
            minute = 0
            meridiem = (groups[1] or "").lower()

        meridiem = meridiem or (hint or "")

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            continue

        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0

        return hour, minute

    return None
