# Phase 1 Agentic AI Receptionist

This module adds the policy-first agent orchestrator on top of the Phase 1 RAG + controlled appointment tools.

## Architecture

`User -> Agent Router -> {RAG | structured tools | safety/handoff} -> grounded response`

The agent never receives a SQL connection, ORM session, repository object, or unrestricted database access. Operational actions are exposed only through the registered tool functions and their Pydantic-validated contracts.

## Routing

- Informational/unknown clinic fact -> RAG; no result -> explicit unavailable response.
- Doctor lookup -> `get_doctors()`.
- Service lookup -> `get_services()`.
- Availability -> `check_availability()` only.
- Booking -> gather required fields -> `check_availability()` -> `book_appointment()`.
- Cancellation/rescheduling -> human support in Phase 1.
- Diagnosis/treatment/prescription/dosage -> safe clinical handoff.

## Context and language

`ConversationState` retains recent turns and booking slots. Language detection supports English, Urdu script, Roman Urdu, and mixed messages. The router is deterministic and policy-first so a generative model cannot bypass safety or transactional rules.

`SYSTEM_PROMPT` is supplied for an optional LLM response generator. Any LLM response must be constrained to RAG context/tool outputs and must never be treated as evidence of availability or booking success.

## Tests

```bash
pytest -q tests/test_agent.py
```

The tests cover English, Urdu, Roman Urdu, mixed-language detection, RAG routing, doctor/service tools, clarification, availability non-hallucination, booking sequencing, unsupported questions, medical safety, and tool failures.
