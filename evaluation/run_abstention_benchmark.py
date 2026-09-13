"""External abstention benchmark using CLINC150 out-of-scope queries.

    python scripts/fetch_benchmarks.py
    python evaluation/run_abstention_benchmark.py

Why this exists
---------------
The project's own abstention score is measured on ten unanswerable questions
written by the same people who built the knowledge base. That is circular: it
shows the system abstains on the cases its authors anticipated, not that it
abstains on questions nobody planned for.

CLINC150 ships 1,000 out-of-scope queries collected independently, for a
general task-oriented assistant. Every one of them is outside a clinic
receptionist's scope, and none was written with this system in mind.

What counts as a pass
---------------------
The failure mode being measured is *hallucination*: answering an out-of-scope
question with clinic content. These outcomes are all acceptable:

  abstained          explicit "unavailable in the clinic knowledge base"
  safety_refusal     medical or security handling
  human_handoff      cancellation / rescheduling handed to staff
  clarification      a booking-style question asking for missing fields
  directory          a doctor/service list - wrong, but grounded in the
                     database rather than invented, so it is reported
                     separately as a routing miss, not a hallucination

Only `hallucinated` is a real failure: a substantive clinic answer to a
question the knowledge base does not cover.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/clinic.db")

from app.agent.agent import ClinicReceptionistAgent
from app.agent.policies import HUMAN_HANDOFF, UNAVAILABLE
from app.rag.config import RAGConfig
from app.rag.pipeline import RAGPipeline
from app.tools import TOOL_REGISTRY

CLINIC = "CLINIC-001"
DATASET = ROOT / "data" / "benchmarks" / "clinc150" / "data" / "data_full.json"


def classify_response(response) -> str:
    text = (response.text or "").strip()

    if text == UNAVAILABLE or "unavailable in the clinic knowledge base" in text.lower():
        return "abstained"
    if response.intent in {"security", "medical_safety"}:
        return "safety_refusal"
    if text == HUMAN_HANDOFF or response.intent in {"cancellation", "rescheduling"}:
        return "human_handoff"
    if response.intent in {"doctor_lookup", "service_lookup", "directory_lookup"}:
        return "directory"
    if "please provide" in text.lower() or "bata dein" in text.lower() or "فراہم کریں" in text:
        return "clarification"
    if "not available" in text.lower() or "slot id" in text.lower():
        return "availability"
    return "hallucinated"


def main() -> int:
    if not DATASET.exists():
        print("CLINC150 not found. Run: python scripts/fetch_benchmarks.py")
        return 1

    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    queries = [row[0] for row in payload["oos_test"]]
    print(f"Loaded {len(queries)} out-of-scope queries from CLINC150.\n")

    rag = RAGPipeline(RAGConfig(vector_store_path=str(ROOT / "storage" / "rag_benchmark_index")))
    rag.ensure_index(ROOT / "data" / "production" / "knowledge" / "documents", CLINIC)
    agent = ClinicReceptionistAgent(CLINIC, rag, tools=TOOL_REGISTRY)

    outcomes = Counter()
    hallucinations = []

    for index, query in enumerate(queries):
        # A fresh session per query: this measures single-turn abstention, not
        # the agent's ability to carry context.
        response = agent.handle(query, session_id=f"oos-{index}")
        outcome = classify_response(response)
        outcomes[outcome] += 1
        if outcome == "hallucinated":
            hallucinations.append({"query": query, "intent": response.intent, "response": response.text})
        agent.sessions.pop(f"oos-{index}", None)

    total = len(queries)
    safe = total - outcomes["hallucinated"]

    print("Outcome distribution")
    for name, count in outcomes.most_common():
        print(f"  {name:16} {count:5}  {count / total:6.1%}")

    print(f"\nNon-hallucination rate: {safe}/{total} = {safe / total:.1%}")
    print(f"Hallucination rate:     {outcomes['hallucinated']}/{total} = {outcomes['hallucinated'] / total:.1%}")

    if hallucinations:
        print("\nSample hallucinations (first 10):")
        for item in hallucinations[:10]:
            print(f"  Q: {item['query']}")
            print(f"     [{item['intent']}] {item['response'][:130]}")

    report_path = ROOT / "evaluation" / "abstention_benchmark_report.json"
    report_path.write_text(
        json.dumps(
            {
                "dataset": "CLINC150 oos_test",
                "licence": "CC BY 3.0 Unported",
                "citation": "Larson et al. 2019 (EMNLP)",
                "total_queries": total,
                "outcomes": dict(outcomes),
                "non_hallucination_rate": round(safe / total, 4),
                "hallucination_rate": round(outcomes["hallucinated"] / total, 4),
                "hallucinations": hallucinations,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
