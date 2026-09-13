"""Audit app/rag/lexicon.py against attested Roman Urdu sources.

    python scripts/fetch_benchmarks.py
    python scripts/audit_lexicon.py

Why this exists
---------------
Every Roman Urdu entry in app/rag/lexicon.py was written from intuition about
how Pakistani users spell things, then validated only against the project's own
40 evaluation queries - which were written by the same hand. That is circular.
This script checks those guesses against two independently compiled sources:

  Conversions/English-Urdu-Roman.txt   ~500 English : Urdu : Roman triples
  Dictionary/Roman-Urdu-Dictionary.txt ~3,300 Roman Urdu headwords with glosses

LICENCE WARNING
---------------
The Roman Urdu Data Set is GPL-3.0, a copyleft licence. This script only
*reads* it to produce a report; it never copies entries into the project. If
you choose to add a suggested term to lexicon.py, you are making a judgement
about whether a single word correspondence is a non-copyrightable fact or a
derivative of a licensed compilation. That is a call for you (and if it
matters commercially, a lawyer) - not something this script does silently.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.lexicon import EXTRA_STOPWORDS, EXTRA_SYNONYMS

BENCH = ROOT / "data" / "benchmarks" / "roman_urdu"
CONVERSIONS = BENCH / "Conversions" / "English-Urdu-Roman.txt"
DICTIONARY = BENCH / "Dictionary" / "Roman-Urdu-Dictionary.txt"

# Concepts the clinic knowledge base actually contains. A suggested term is
# only interesting if it maps onto one of these.
CLINIC_CONCEPTS = {
    "time", "hour", "hours", "day", "days", "morning", "evening", "night",
    "doctor", "physician", "medicine", "treatment", "disease", "patient",
    "appointment", "meeting", "money", "price", "fee", "cost", "payment",
    "cash", "address", "phone", "contact", "open", "closed", "week", "month",
    "today", "tomorrow", "yesterday", "language", "help", "staff", "office",
}


def load_conversions() -> dict[str, str]:
    """Roman token -> English gloss, from 'English : Urdu : Roman' lines."""
    pairs = {}
    if not CONVERSIONS.exists():
        return pairs
    for line in CONVERSIONS.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = [p.strip() for p in line.split(":")]
        if len(parts) != 3:
            continue
        english, _urdu, roman = parts
        if roman:
            pairs[roman.lower()] = english.lower()
    return pairs


def load_dictionary() -> dict[str, str]:
    """Roman headword -> gloss, from 'headword: gloss' lines."""
    entries = {}
    if not DICTIONARY.exists():
        return entries
    for line in DICTIONARY.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        head, gloss = line.split(":", 1)
        head = head.strip().lower()
        if head and re.fullmatch(r"[a-z'\-]+", head):
            entries.setdefault(head, gloss.strip().lower())
    return entries


def main() -> int:
    if not CONVERSIONS.exists() and not DICTIONARY.exists():
        print("Roman Urdu benchmark not found. Run: python scripts/fetch_benchmarks.py")
        return 1

    conversions = load_conversions()
    dictionary = load_dictionary()
    attested = set(conversions) | set(dictionary)
    print(f"Attested Roman Urdu headwords: {len(attested)} "
          f"({len(conversions)} conversions, {len(dictionary)} dictionary)\n")

    roman_synonyms = {k: v for k, v in EXTRA_SYNONYMS.items() if re.fullmatch(r"[a-z]+", k)}
    roman_stopwords = {w for w in EXTRA_STOPWORDS if re.fullmatch(r"[a-z]+", w)}

    def report(label, terms):
        confirmed = sorted(t for t in terms if t in attested)
        unconfirmed = sorted(t for t in terms if t not in attested)
        total = len(terms)
        rate = len(confirmed) / total if total else 0.0
        print(f"{label}: {len(confirmed)}/{total} attested ({rate:.0%})")
        if confirmed:
            print(f"  confirmed:   {', '.join(confirmed[:22])}"
                  f"{' ...' if len(confirmed) > 22 else ''}")
        if unconfirmed:
            print(f"  unattested:  {', '.join(unconfirmed[:22])}"
                  f"{' ...' if len(unconfirmed) > 22 else ''}")
        print()
        return confirmed, unconfirmed

    print("=" * 72)
    print("PART 1 - are my hand-written entries real Roman Urdu?")
    print("=" * 72)
    report("Synonym keys", set(roman_synonyms))
    report("Stopwords", roman_stopwords)

    print("=" * 72)
    print("PART 2 - clinic-relevant terms present in the sources but NOT in lexicon.py")
    print("=" * 72)
    known = set(roman_synonyms) | roman_stopwords
    suggestions: list[tuple[str, str]] = []
    for roman, gloss in sorted({**dictionary, **conversions}.items()):
        if roman in known or len(roman) < 3:
            continue
        gloss_tokens = set(re.findall(r"[a-z]+", gloss))
        hit = gloss_tokens & CLINIC_CONCEPTS
        if hit:
            suggestions.append((roman, gloss[:58]))

    print(f"{len(suggestions)} candidate term(s). Review before adding - see the")
    print("licence warning at the top of this file.\n")
    for roman, gloss in suggestions[:45]:
        print(f"  {roman:18} {gloss}")
    if len(suggestions) > 45:
        print(f"  ... and {len(suggestions) - 45} more")

    report_path = ROOT / "evaluation" / "lexicon_audit_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"Attested headwords: {len(attested)}\n\n")
        f.write("UNATTESTED LEXICON ENTRIES (may still be valid informal spellings)\n")
        for term in sorted(set(roman_synonyms) | roman_stopwords):
            if term not in attested:
                f.write(f"  {term}\n")
        f.write("\nCANDIDATE ADDITIONS (clinic-relevant, not yet in lexicon.py)\n")
        for roman, gloss in suggestions:
            f.write(f"  {roman:20} {gloss}\n")
    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
