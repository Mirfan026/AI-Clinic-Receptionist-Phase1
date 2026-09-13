"""Regression tests for deterministic date handling and booking parsing.

These cover the Phase B/C fixes: relative dates must resolve through Python
date arithmetic in Asia/Karachi, and booking fields must accumulate across
turns without ever inventing a time or accepting an unverified patient ID.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.agent.dates import CLINIC_TZ, parse_clock_time, resolve_relative_date
from app.agent.parsing import (
    looks_like_bare_id_attempt,
    parse_date,
    parse_datetime,
    parse_patient_id,
)

# A fixed Wednesday, so every expectation below is independent of the run date.
NOW = datetime(2026, 9, 16, 10, 0, tzinfo=ZoneInfo("Asia/Karachi"))


def test_clinic_timezone_is_karachi():
    assert CLINIC_TZ.key == "Asia/Karachi"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what are the clinic timings today?", "2026-09-16"),
        ("aaj clinic khula hai?", "2026-09-16"),
        ("آج کلینک کھلا ہے؟", "2026-09-16"),
        ("what are the clinic timings tomorrow?", "2026-09-17"),
        ("kal ki kia timing hay", "2026-09-17"),
        ("aglay din appointment", "2026-09-17"),
        ("I was there yesterday", "2026-09-15"),
        ("day after tomorrow", "2026-09-18"),
        ("parson aana hai", "2026-09-18"),
    ],
)
def test_relative_expressions_resolve(text, expected):
    resolved = resolve_relative_date(text, NOW)
    assert resolved is not None
    assert resolved.iso == expected


def test_kal_uses_tense_to_choose_direction():
    """Urdu 'kal' is symmetric; past-tense markers must resolve backwards."""
    assert resolve_relative_date("kal 2:30 pm aana hai", NOW).iso == "2026-09-17"
    assert resolve_relative_date("kal clinic band tha", NOW).iso == "2026-09-15"


def test_next_weekday_resolves_forward():
    resolved = resolve_relative_date("next Monday", NOW)
    assert resolved.iso == "2026-09-21" and resolved.weekday == "Monday"


def test_bare_weekday_is_not_a_relative_date():
    """Bare weekday names are answered from the knowledge base, not rewritten."""
    assert resolve_relative_date("What are your Saturday timings?", NOW) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2:30 pm", (14, 30)),
        ("at 10:00", (10, 0)),
        ("subah 10 baje", (10, 0)),
        ("shaam 5 baje", (17, 0)),
    ],
)
def test_clock_times(text, expected):
    assert parse_clock_time(text) == expected


def test_stray_numbers_are_not_times():
    """A schedule id must never be reinterpreted as a clock time."""
    assert parse_clock_time("schedule_id=75") is None
    assert parse_clock_time("P-001") is None


def test_iso_date_with_separated_time():
    assert parse_datetime("on 2026-09-16 at 10:00") == datetime(2026, 9, 16, 10, 0)


def test_relative_date_with_time():
    assert parse_datetime("kal 2:30 pm", NOW) == datetime(2026, 9, 17, 14, 30)


def test_relative_date_without_time_is_not_a_datetime():
    """A date alone must not become a booking instant with an invented time."""
    assert parse_datetime("kal appointment book karna hai", NOW) is None
    assert parse_date("kal appointment book karna hai", NOW).isoformat() == "2026-09-17"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("P-001", "P-001"),
        ("patient PATIENT-001 please", "P-001"),
        ("p-012", "P-012"),
    ],
)
def test_patient_ids_are_normalised(text, expected):
    assert parse_patient_id(text) == expected


@pytest.mark.parametrize("text", ["11222", "111111", "my id is 7", "schedule_id=75"])
def test_bare_numbers_are_never_patient_ids(text):
    assert parse_patient_id(text) is None


def test_bare_id_attempt_detected():
    assert looks_like_bare_id_attempt("11222")
    assert not looks_like_bare_id_attempt("P-001")


def test_index_is_rebuilt_only_when_corpus_changes(tmp_path):
    from pathlib import Path

    from app.rag.config import RAGConfig
    from app.rag.pipeline import RAGPipeline

    docs = Path(__file__).resolve().parents[1] / "data/production/knowledge/documents"
    config = RAGConfig(
        vector_store_path=str(tmp_path / "vs"),
        embedding_backend="tfidf",
    )

    first = RAGPipeline(config).ensure_index(docs, "CLINIC-001")
    assert first["rebuilt"] is True

    second = RAGPipeline(config).ensure_index(docs, "CLINIC-001")
    assert second["rebuilt"] is False
    assert second["fingerprint"] == first["fingerprint"]


# ---------------------------------------------------------------------------
# Regressions found by auditing the lexicon against the Roman Urdu Data Set
# (data/benchmarks/roman_urdu). See scripts/audit_lexicon.py.
# ---------------------------------------------------------------------------

def test_aglay_hafta_means_next_week_not_saturday():
    """Urdu 'hafta' is both 'week' and 'Saturday'.

    Qualified by 'aglay' it means next week. Before this was handled, an
    appointment request for 'aglay hafta' silently resolved to the coming
    Saturday - a wrong date offered with full confidence.
    """
    assert resolve_relative_date("aglay hafta appointment", NOW).iso == "2026-09-23"
    assert resolve_relative_date("next week", NOW).iso == "2026-09-23"
    # A qualified weekday must still resolve to that weekday.
    assert resolve_relative_date("aglay itwar", NOW).weekday == "Sunday"


def test_subh_variant_sets_morning():
    """'subh' is the attested spelling; only 'subah' was recognised before,
    so 'subh 6 baje' fell through to the afternoon default and became 18:00."""
    assert parse_clock_time("subh 6 baje") == (6, 0)
    assert parse_clock_time("subah 6 baje") == (6, 0)
    assert parse_clock_time("shaam 6 baje") == (18, 0)


def test_attested_roman_spellings_route_correctly():
    from app.agent.router import classify
    assert classify("mulaaqaat chahiye").intent == "booking"
    assert classify("clinic ke auqaat kya hain").intent == "information"
