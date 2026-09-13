# AI Clinic Receptionist & Appointment Assistant — Phase 1

A multilingual AI receptionist for **Maple Crescent Family Clinic** (synthetic).
It answers clinic questions from a knowledge base, finds doctors and services,
checks **real** appointment availability, and books appointments through
transactional database operations — in English, Urdu, Roman Urdu, or a mix.

**Status:** Phase 1 MVP, locally runnable, no external API key required.

| Metric | Result |
|---|---|
| Unit / integration tests | **101 passed** |
| Agent evaluation cases | **41 / 41** |
| End-to-end QA | **40 / 40** |
| RAG retrieval & grounding | **100 %** (40/40) |
| Safety | **100 %** |
| Intent / entity / context / language | **100 %** |
| Tool selection | **92.5 %** (see *Known limitations*) |
| CLINC150 out-of-scope hallucination rate | **0 / 1000** |

---

## The central design rule

> **RAG answers static clinic knowledge. The database is the only authority on
> live operational data.**

The assistant will never tell you a slot is free because a document implied it,
and never says an appointment is booked unless `book_appointment()` returned
`success=true`. Dates are resolved with Python arithmetic, not by a language
model, so "kal" cannot drift into the wrong day.

---

## Architecture

```
          ┌──────────────────────────────────────────┐
          │            Streamlit UI                  │
          │   chat · workflow trace · source panel   │
          └───────────────────┬──────────────────────┘
                              │  (no booking or retrieval logic lives here)
          ┌───────────────────▼──────────────────────┐
          │                 Agent                    │
          │  language · safety · routing · state     │
          │  deterministic date & entity resolution  │
          └────────┬────────────────────┬────────────┘
                   │                    │
      ┌────────────▼─────────┐   ┌──────▼───────────────────────┐
      │        RAG           │   │      Controlled tools        │
      │ static knowledge     │   │ get_doctors · get_services   │
      │ retrieval+grounding  │   │ check_availability · book_…  │
      └────────────┬─────────┘   └──────┬───────────────────────┘
                   │                    │
      ┌────────────▼─────────┐   ┌──────▼───────────────────────┐
      │   Knowledge base     │   │  Repositories → SQLite DB    │
      │   15 markdown docs   │   │  transactional booking       │
      └──────────────────────┘   └──────────────────────────────┘
```

A modular monolith. No microservices, no Kubernetes, no event bus.

### Layer responsibilities

| Layer | Responsibility | Never does |
|---|---|---|
| `app/ui` | Presentation, chat, admin view | Booking logic, retrieval, prompt building |
| `app/agent` | Language, safety, routing, state, orchestration | Direct SQL or ORM access |
| `app/rag` | Chunking, embedding, retrieval, grounding, abstention | Decide availability |
| `app/tools` | Schema-validated, allowlisted operations | Run unvalidated input |
| `app/database` | Models, constraints, transactional repositories | Know about agents or prompts |

---

## Setup

**Requirements:** Python 3.11+ (3.12 recommended).

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts/seed_database.py
pytest -q
streamlit run streamlit_app.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

python scripts/seed_database.py
pytest -q
streamlit run streamlit_app.py
```

The UI starts at <http://localhost:8501>.

`setup_windows.bat` and `run_demo.bat` wrap the same steps for Windows users.

### API keys

**None are required.** Phase 1 runs entirely locally on deterministic agent
logic, RAG, and SQLite. Do not add an LLM key to make dates or entity
extraction work — that would make the system *less* reliable and would break
the rule that the model never decides operational facts.

If you add an external LLM later, read the key from `.env` (see `.env.example`)
and never commit it.

---

## Running the evaluations

```bash
python evaluation/run_complete_agent_eval.py   # 41 agent cases + 40 RAG cases
python evaluation/run_e2e_qa.py                # 40 end-to-end scenarios
python scripts/validate_database.py            # schema and constraint checks
pytest -q                                      # 101 unit/integration tests

# External benchmarks (downloads third-party data - see BENCHMARKS.md)
python scripts/fetch_benchmarks.py
python evaluation/run_abstention_benchmark.py  # CLINC150: 1,000 out-of-scope queries
python scripts/audit_lexicon.py                # lexicon vs attested Roman Urdu
```

Reports are written to `evaluation/`.

### Embedding backends

Retrieval uses a multilingual SentenceTransformer
(`paraphrase-multilingual-mpnet-base-v2`) when it can be downloaded, and falls
back to a deterministic TF-IDF vectoriser otherwise. Both paths are supported.
**Scores differ between backends**, so state which one you used when reporting
numbers. The headline results above were produced on the TF-IDF fallback; re-run
locally to confirm on the SentenceTransformer path.

Vector storage prefers ChromaDB and falls back to a persistent NumPy index.

---

## What the assistant handles

**Information** — timings, fees, payment methods, contact details, policies,
in any of the four supported language modes.

**Relative dates** — `today`, `tomorrow`, `yesterday`, `day after tomorrow`,
`next Monday`, and the Urdu/Roman-Urdu equivalents `aaj`/`آج`, `kal`/`کل`,
`parson`/`پرسوں`, `aglay din`. Resolved in `Asia/Karachi`.

`kal` and `parson` mean both directions in Urdu; the resolver reads tense
markers and otherwise looks forward, which is the right default at a front
desk:

```
"kal 2:30 pm aana hai"   → tomorrow
"kal clinic band tha"    → yesterday   (past-tense "tha")
```

**Directory lookups** — doctors and services, always through controlled tools.

**Availability and booking** — multi-turn, with fields accumulated across
turns. A date without a time is remembered but never completed with a guessed
time.

**Safety** — refuses diagnosis, treatment, prescriptions and dosage; resists
prompt injection, secret extraction and SQL/tool abuse; treats retrieved
documents as untrusted data, never as instructions.

**Abstention** — unsupported questions ("Do you have parking?") get an explicit
*unavailable* answer rather than a plausible invention.

---

## Known limitations

**Tool selection scores 92.5 %, not 100 %, and this is intentional.** Three
evaluation cases ask the agent to *clarify* a booking while also expecting it to
have extracted `doctor_id: DR-001` from the text "Dr Amina". Resolving a name to
an ID requires calling `get_doctors()` — the directory must not be answered from
model memory. The evaluator counts that call against tool selection. Raising
this metric would mean either inventing doctor IDs or dropping entity extraction
from 100 %. The behaviour is correct; the metric is the compromise.

**Cancellation and rescheduling are human handoffs.** Phase 1 deliberately does
not mutate existing appointments from conversation.

**The admin dashboard reads the ORM directly.** Acceptable for a demo; a
production deployment needs authentication, RBAC, audit logging and tenant
scoping.

**Language detection is heuristic.** Token-based classification can misjudge
heavily code-switched text.

**The knowledge base is small and synthetic** (15 documents). Retrieval quality
on a real corpus would need re-tuning.

**The new dataset feature columns are groundwork, not live behaviour.** The
agent reads none of `preferred_language`, `payment_status`, `booking_channel`
and the rest. They exist so the admin view and Phase 2 analytics have real data
to work with. See `DATASETS.md`.

---

## Future work

- Dense multilingual reranking and a larger evaluation corpus
- Cancellation and rescheduling as transactional tools with audit trails
- Patient identity verification before disclosing appointment details
- Authenticated, role-scoped admin interface
- Structured observability for tool calls and grounding decisions

---

## Documentation map

| File | Contents |
|---|---|
| `README_DATABASE.md` | Schema, constraints, transactional booking |
| `README_RAG.md` | Retrieval pipeline and grounding |
| `README_AGENT.md` | Routing, state, orchestration |
| `README_TOOLS.md` | Tool contracts and error codes |
| `README_SAFETY.md` | Safety model and threat handling |
| `README_UI.md` | Streamlit layer |
| `DATASETS.md` | Dataset schema, balance targets and regeneration |
| `BENCHMARKS.md` | External benchmarks, licences and results |
| `PHASE1_CHANGELOG.md` | Root causes and fixes in this revision |
| `DEMO_SCRIPT.md` | Suggested live demo walkthrough |
| `GITHUB_BEGINNER_GUIDE.md` | Publishing to GitHub |
| `BEGINNER_SETUP_WINDOWS.md` | Windows/VS Code setup |

---

## Disclaimer

Administrative and informational assistant only. It does not diagnose, treat,
or prescribe. All clinic, doctor, service and patient data is synthetic.
