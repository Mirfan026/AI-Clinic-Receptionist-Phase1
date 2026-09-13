# External benchmarks

The project's own evaluation suites were written by the same people who built
the knowledge base. That makes them good regression tests and weak evidence:
they show the system handles the cases its authors anticipated. These external
datasets test it against data nobody here wrote.

```bash
python scripts/fetch_benchmarks.py          # downloads into data/benchmarks/
python evaluation/run_abstention_benchmark.py
python scripts/audit_lexicon.py
```

`data/benchmarks/` is gitignored. The datasets are **not** vendored into this
repository: they carry their own licences, one of them copyleft, and the
project should not inherit those obligations silently. Every download records
its licence in `data/benchmarks/MANIFEST.json`.

## What is used

| Dataset | Licence | Used for |
|---|---|---|
| **CLINC150** (`clinc/oos-eval`) | CC BY 3.0 | Out-of-scope abstention stress test |
| **Roman Urdu Data Set** (`Smat26/Roman-Urdu-Dataset`) | **GPL-3.0** | Auditing `app/rag/lexicon.py` |
| **Schema-Guided Dialogue** (train schema) | CC BY-SA 4.0 | Booking-contract comparison |

Citations: Larson et al. 2019 (EMNLP); Sharf, Z., Roman Urdu Data Set;
Rastogi et al. 2019.

> **Licence warning.** The Roman Urdu Data Set is GPL-3.0, a copyleft licence.
> `scripts/audit_lexicon.py` only *reads* it to produce a report; it never
> copies entries into the project. If you add a suggested term to
> `lexicon.py`, you are judging whether a single word correspondence is an
> uncopyrightable fact or a derivative of a licensed compilation. That is your
> call, and a lawyer's if it ever matters commercially. Nothing in this repo
> makes it for you.

## Result 1 — abstention against 1,000 independent queries

CLINC150 ships 1,000 out-of-scope queries collected for a general
task-oriented assistant. All of them fall outside a clinic receptionist's
scope, and none was written with this system in mind.

| Outcome | Count | Share |
|---|---:|---:|
| Abstained explicitly | 939 | 93.9% |
| Routed to directory tools | 29 | 2.9% |
| Asked for booking details | 21 | 2.1% |
| Safety refusal | 9 | 0.9% |
| Human handoff | 2 | 0.2% |
| **Hallucinated a clinic fact** | **0** | **0.0%** |

**Hallucination rate: 0 / 1000.**

Read the 6.1% that did not abstain carefully before quoting this. Those are
**routing misses, not fabrications**. A query containing "doctor" or "book"
reaches a directory tool or a booking clarification, so the answer is grounded
in the database rather than invented. Wrong lane, but nothing made up — which
is the property that actually matters here.

For calibration: the CLINC150 paper reports BERT reaching high-80s to mid-90s
in-scope accuracy while out-of-scope *recall* tops out around 66%. The
comparison is not like-for-like — that is a 151-way classifier, this is a
grounding gate with a hard abstention threshold — so do not present 100% as
beating a published baseline. It is a different measurement of a related
property.

## Result 2 — auditing the lexicon against attested Roman Urdu

`scripts/audit_lexicon.py` checks every hand-written Roman Urdu entry in
`app/rag/lexicon.py` against ~1,400 attested headwords.

| Set | Attested |
|---|---|
| Synonym keys | 5 / 69 (7%) |
| Stopwords | 2 / 105 (2%) |

**This is not evidence that 93% of the lexicon is wrong.** The source is a
formal literary dictionary — *aabru*, *aatish*, *zamaanah*. The lexicon
deliberately targets informal chat spellings — *hay*, *kia*, *btao*, *mujhy* —
which a formal dictionary will never contain. The registers do not overlap, so
a low attestation rate is the expected result.

What it does establish is the real limitation: **the lexicon still has no
independent validation.** Confirming informal spellings needs a corpus of
actual Pakistani chat text, not a dictionary. The 20,000 tagged sentences in
the same repository are the obvious next step, and were not used here.

### Four real bugs the audit found

| Finding | Before | After |
|---|---|---|
| `hafta` means both "week" and "Saturday" | "aglay hafta" → next **Saturday** | → **+7 days** |
| `subh` is the attested spelling of `subah` | "subh 6 baje" → **18:00** | → **06:00** |
| `mulaaqaat` (Roman) absent; only Urdu script covered | routed to `unknown` | → `booking` |
| `auqaat` (Roman) absent; only Urdu script covered | routed to `unknown` | → `information` |

The first two were silently wrong answers, not crashes. "Aglay hafta" would
have offered a confident appointment on the wrong day. Covered now by
`tests/test_dates.py`.

## Result 3 — the booking contract matches SGD

SGD's `Services_3` is a doctor-appointment service. Its schema marks
`BookAppointment` as `is_transactional: true` with required slots that must be
filled before the API call executes.

| | SGD `Services_3` | This project |
|---|---|---|
| Transactional intent | `BookAppointment` | `book_appointment()` |
| Required before call | `doctor_name`, `appointment_date`, `appointment_time` | doctor, service, patient, date+time |
| Non-transactional search | `FindProvider` | `check_availability()` |

The gate — collect required slots, search, then commit — is the same design an
established benchmark encodes. This project adds `service` and `patient_id`
because booking is validated against real doctor–service relationships and a
registered patient.

No SGD dialogues were run. Its schema is used as an architectural reference
only; the dataset is English and its label space does not match this system's.

## Not used, and why

**MASSIVE** (Amazon, 51 languages including `ur-PK`) is the best available
Urdu intent/slot resource and would be the highest-value next step. It could
not be fetched here: it is hosted on S3 and HuggingFace, both unreachable from
the build environment. On an unrestricted machine, `scripts/fetch_benchmarks.py`
is the right place to add it. Note that its 60 intents do not align with this
system's ~9, so it cannot be scored directly — its value is as a source of
real Urdu phrasings.

**MIRACL** does not include Urdu. Its 18 languages are ar, bn, de, en, es, fa,
fi, fr, hi, id, ja, ko, ru, sw, te, th, yo, zh. Hindi shares the spoken
language but not the script; Persian shares the script but not the language.

**MedQA / PubMedQA** test medical knowledge this system deliberately refuses to
have. Scoring badly on them would be the safety design working correctly.

**MIMIC-III / MIMIC-IV** require PhysioNet credentialing and a data use
agreement. This project needs no real patient data; synthetic data is the
correct choice here, not a compromise.

## The rule that must not be broken

Nothing in `data/benchmarks/` may ever be copied into
`data/production/knowledge/documents/`. Benchmarks are evaluation inputs.
Enlarging the knowledge base with benchmark text would destroy the abstention
behaviour these benchmarks exist to measure — and would turn a genuine 0/1000
into a meaningless one.
