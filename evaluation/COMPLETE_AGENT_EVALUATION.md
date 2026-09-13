# Complete AI Receptionist Multilingual Evaluation

## Scope

41 agent cases (40 single-turn + 1 multi-turn booking-context case) plus the
40-case RAG evaluation dataset. Languages: English, Urdu, Roman Urdu, and
mixed/code-switched input.

Reproduce with:

```bash
python scripts/seed_database.py
python evaluation/run_complete_agent_eval.py
```

## Final results

| Dimension | Score |
|---|---|
| Intent detection | 1.0 |
| Entity extraction | 1.0 |
| Tool selection | 0.925 |
| Response language | 1.0 |
| RAG retrieval and grounding | **1.0** |
| Conversation context | 1.0 |
| Safety | 1.0 |
| Overall agent case pass rate | 1.0 |
| Overall cases | 41 |
| RAG cases | 40 |

Supporting suites:

| Suite | Result |
|---|---|
| `pytest -q` | 98 passed |
| `evaluation/run_e2e_qa.py` | 40 / 40 |
| `scripts/run_rag_evaluation.py` | source hit rate 1.0, unanswerable rejection 1.0 |
| `scripts/validate_database.py` | passed |

Per-language retrieval accuracy from `scripts/run_rag_evaluation.py`:
English 1.0, Urdu 1.0, Roman Urdu 1.0, Mixed 1.0.

## Embedding backend

These figures were produced on the **deterministic TF-IDF fallback**, because
the SentenceTransformer model could not be downloaded in the environment where
the run was executed. Both backends are supported and scores differ between
them. Always record which backend produced a number.

An earlier handoff recorded 87.5% in one run and 82.5% in another. That gap was
not a regression: the ChromaDB collection holds 768-dimension vectors
(SentenceTransformer) while the NumPy index holds 4474-dimension vectors
(TF-IDF). The two figures came from two backends.

## Interpretation

All 41 agent cases pass. Safety and hallucination-abstention checks are
fail-closed, and all ten unanswerable cases still return an explicit
*unavailable* response rather than a plausible invention.

RAG reached 100% by fixing retrieval defects, **not** by relaxing thresholds.
`similarity_threshold` and the 0.75 grounding-coverage rule are unchanged from
the previous revision. The decisive fix was widening the retrieval candidate
pool: the lexical re-ranker was only ever shown 10 candidates, so for
cross-lingual queries - where every English chunk scores near zero semantically
- the correct document could be discarded before it was ever scored.

Root causes and fixes for every change are documented in `PHASE1_CHANGELOG.md`.

## Why tool selection is 0.925 and not 1.0

Three cases (E21, E22, E24) expect a booking *clarification* while also
expecting `doctor_id: DR-001` to have been extracted from the text "Dr Amina".
Resolving a human-readable name to an ID requires calling `get_doctors()`,
because the doctor directory must never be answered from model memory. The
evaluator counts that call against tool selection.

Raising this metric would require either inventing doctor IDs or abandoning
entity extraction, which currently scores 1.0. The behaviour is correct; the
metric is the compromise. This is a limitation of the evaluator's scoring
model, not of the agent.

## Remaining model-quality notes

- The knowledge base is small (15 synthetic documents). Retrieval quality on a
  real corpus would need re-tuning and a larger benchmark.
- Language classification is heuristic and can misjudge heavily code-switched
  text.
- Production should use multilingual dense embeddings with a reranker, and
  continue expanding Urdu and Roman Urdu paraphrase coverage, while keeping the
  deterministic abstention rule intact.
