# Phase 1 — root causes and fixes

Every change below was made against a reproduced failure, with `pytest -q` and
`evaluation/run_complete_agent_eval.py` re-run afterwards.

## Baseline before this revision

```
pytest                      68 passed
agent cases                 41 / 41
rag_retrieval_and_grounding 0.875   (TF-IDF backend)
tool_selection              0.925
safety / intent / entity / context  1.0
```

## Result after this revision

```
pytest                      98 passed   (68 original + 30 new)
agent cases                 41 / 41
end-to-end QA               40 / 40
rag_retrieval_and_grounding 1.000
tool_selection              0.925       (unchanged — see README limitations)
safety / intent / entity / context  1.0
```

---

## 1. Relative dates returned "information unavailable"

**Reported:** `kal ki kia timing hay` and `what are the tomorrow timing` both
answered *The information is unavailable in the clinic knowledge base*, even
though clinic timings are in the knowledge base.

**Root cause — two independent faults.**

`parse_datetime` recognised only `tomorrow|kal|کل|today|aaj|آج` and required a
clock time in the same message, so a timing question produced no date at all.

Separately, `grounding.extractive_answer` treated `kal`, `ki`, `kia`, `hay` as
content words. Its coverage rule requires 75 % of query tokens to appear in the
retrieved context; Roman Urdu grammatical particles can never appear in an
English document, so coverage collapsed and the grounded answer was discarded.

**Fix.** New `app/agent/dates.py` resolves relative expressions with Python
date arithmetic in `Asia/Karachi`. The agent substitutes the resolved weekday
into the query before retrieval and prefixes the resolved date onto the answer,
so the knowledge base still supplies the hours themselves. Roman Urdu and Urdu
function words moved into a shared stop-word list.

**Files:** `app/agent/dates.py` (new), `app/agent/parsing.py`,
`app/agent/agent.py`, `app/rag/lexicon.py` (new).

---

## 2. RAG retrieval capped at 87.5 %

**Root cause — the lexical re-ranker was starved.** `Retriever.retrieve`
requested `max(top_k, 10)` candidates from the vector store, then re-ranked them
lexically. For a cross-lingual query every English chunk scores approximately
zero semantically, so the candidate pool was effectively arbitrary and the
correct document was discarded *before* the lexical stage could score it.
`rescheduling_policy.md` never reached the re-ranker for the Urdu rescheduling
question.

Three smaller faults compounded it:

- `source_lexical` was computed and then thrown away; the comment above it
  described a boost the code never applied.
- Arabic question and full-stop marks fall inside the `\u0600-\u06ff` range, so
  `ہے؟` tokenised as one word and never matched the `ہے` stop-word entry.
- The knowledge base names specialties (*Dermatology*) while users name body
  parts (*skin doctor*), with no mapping between them.

**Fix.** Widened the candidate pool, applied `source_lexical` as a bounded
tie-breaker, stripped Arabic punctuation during tokenisation, and added a shared
translation lexicon.

**Thresholds were not touched.** `similarity_threshold` and the 0.75 coverage
rule are unchanged, and all ten abstention cases still abstain.

**Files:** `app/rag/retriever.py`, `app/rag/grounding.py`, `app/rag/lexicon.py`.

---

## 3. Booking lost the time from "on 2026-09-16 at 10:00"

**Root cause.** The ISO pattern required date and time to be adjacent. With
`at` between them it fell through to the date-only branch and booked against
midnight.

**Fix.** Parse date and clock time independently and combine them.

**Files:** `app/agent/parsing.py`, `app/agent/dates.py`.

---

## 4. Bare numbers were silently treated as patient IDs

**Reported:** typing `11222` produced the same clarification repeatedly with no
explanation.

**Root cause.** Patient extraction used a loose prefix search and had no
feedback path for a malformed ID.

**Fix.** Patient IDs must match `P-###` / `PATIENT-###` and normalise to the
`P-###` form the database actually stores. A bare number now gets an explicit
correction. Existence is still verified by the database inside
`book_appointment()`, and `PATIENT_NOT_FOUND` now produces an actionable
message instead of a generic failure.

**Files:** `app/agent/parsing.py`, `app/agent/agent.py`.

---

## 5. Multi-turn booking collapsed on short replies

**Root cause.** Booking context was carried over only when the router returned
`unknown`. A reply of `Cardiology` classified as `service_lookup` and dumped the
entire service directory, discarding the booking in progress. `kal` classified
as `information` and answered a timings question instead of filling the date.

**Fix.** An explicit `booking_active` flag, independent of `last_intent`. A turn
continues the booking when it supplies a bookable field and carries no
new-question marker. Safety, medical and cancellation routes always take
precedence, and the collected fields are cleared once a booking commits.

A genuine question mid-booking is now answered *and* the booking survives it.

**Files:** `app/agent/agent.py`.

---

## 6. A date without a time could not be supplied separately

**Fix.** A date alone is stored as `booking_date`; a later clock time completes
it into `start_at`. A date is never completed with a guessed time.

**Files:** `app/agent/agent.py`.

---

## 7. Unavailable times were not stated as such

**Root cause.** When the requested slot was unavailable, the agent listed
alternatives without saying the requested time had failed.

**Fix.** The agent now names the unavailable time before listing
database-returned alternatives, localised, capped at ten.

**Files:** `app/agent/agent.py`.

---

## 8. Non-English clarifications dropped the missing-field list

**Root cause.** `_clarification` returned a generic sentence for Urdu, Roman
Urdu and mixed, so non-English users were told to "provide the required
information" without being told which fields were missing.

**Fix.** Localised field names and worked examples in all four modes.

**Files:** `app/agent/agent.py`.

---

## 9. A stale vector index could answer from outdated documents

**Root cause.** The UI re-ingested only when `index.json` was absent, so an
index built from older documents, a different chunk size, or a different
embedding backend would be reused silently.

**Fix.** `RAGPipeline.ensure_index()` fingerprints chunk configuration,
embedding backend, vector store class and every source file's size and mtime,
and rebuilds when any of them change. Nothing is deleted.

**Files:** `app/rag/pipeline.py`, `app/ui/streamlit_app.py`.

---

## 10. Streamlit deprecation warning

`use_container_width` replaced with `width="stretch"` in three places.

**Files:** `app/ui/streamlit_app.py`.

---

## 11. Datasets were unbalanced and had no history

**Root cause.** The seeded dataset exercised only a fraction of its own schema:
3 of 5 doctors and 7 of 9 services had zero appointments, and the statuses
`scheduled`, `completed` and `no_show` never appeared. The underlying reason for
the last three is that every slot was in the future, which makes a completed or
missed appointment logically impossible.

**Fix.** `scripts/generate_datasets.py` regenerates the production CSVs
deterministically: 60 patients, 1,932 schedules, 251 appointments, four weeks of
history plus six weeks forward. Load is 50-51 appointments per doctor with
exactly 10 of each status each. New feature columns were added to all five
tables. Full detail in `DATASETS.md`.

**Files:** `scripts/generate_datasets.py` (new), `data/production/*.csv`,
`app/database/models.py`, `scripts/seed_database.py`, `DATASETS.md` (new).

---

## 12. Schedules contradicted the published clinic hours

**Root cause.** 32 schedule rows offered bookable slots between 13:00 and 14:00,
inside the administrative break that `clinic_timings.md` documents. The database
would have offered appointments during a window the assistant correctly
described as closed.

**Fix.** Those rows are now `blocked` with `slot_type='admin_break'`. They are
blocked rather than deleted so their surrogate ids, referenced by the evaluation
suites, survive.

**Files:** `data/production/doctor_schedules.csv`, `scripts/generate_datasets.py`.

---

## 13. Database validation asserted row counts instead of invariants

**Root cause.** `scripts/validate_database.py` hard-coded `schedules: 372,
patients: 12, appointments: 24`, so it failed the moment the dataset grew while
checking almost nothing that mattered.

**Fix.** Rewritten to assert structure: referential integrity between
appointments, schedules and doctor-service pairs; one active appointment per
slot; complete status vocabularies; no idle doctor or service; and no bookable
slot outside clinic hours. Only genuinely fixed counts (1 clinic, 5 doctors,
9 services) are still exact.

**Files:** `scripts/validate_database.py`.

---

## Note on the two historical RAG scores

The handoff recorded 87.5 % in one run and 82.5 % in another and asked which was
current. Neither was a regression: `storage/rag_vector_store/chroma.sqlite3`
holds 768-dimension vectors (SentenceTransformer) while `index.json` holds
4474-dimension vectors (TF-IDF). The two figures come from two embedding
backends. Always record which backend produced a score.

---

## Invariants preserved

| # | Invariant | Status |
|---|---|---|
| 1 | RAG never determines live availability | Held |
| 2 | Model never modifies the database | Held |
| 3 | Booking succeeds only on `success=true` | Held |
| 4 | Unknown tools cannot execute | Held |
| 5 | Clinic scope cannot be bypassed | Held |
| 6 | Retrieved documents are untrusted data | Held |
| 7 | Unsupported questions are not answered | Held — 10/10 abstain |
| 8 | Safety remains 100 % | Held |
| 9 | The original 68 tests still pass | Held — 98 pass |
| 10 | Architecture stays modular | Held — no layer moved |
