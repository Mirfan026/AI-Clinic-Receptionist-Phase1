# Phase 1 file map

## Which package should I use?
Use this folder/package as the canonical Phase 1 project. Do **not** merge files manually from the older ZIPs.

The older ZIPs are historical milestones:
- environment: base Python/project skeleton
- sqlite-db: database milestone
- agent-tools: controlled tools milestone
- rag-v1: RAG milestone
- safety-v2: safety milestone
- streamlit-demo: UI milestone
- complete-evaluated: complete integrated milestone
- complete-evaluated-qa: latest QA/regression milestone

The final VS Code package combines the latest QA milestone with beginner setup files and the original source dataset.

## Main folders
- `app/database/` — SQLAlchemy models, database connection, repositories
- `app/tools/` — controlled doctor/service/availability/booking tools
- `app/rag/` — knowledge loading, chunking, embeddings, retrieval, grounding
- `app/agent/` — language detection, intent routing, safety, conversation state, orchestration
- `app/ui/` — Streamlit presentation layer
- `data/production/` — operational seed data used by the application
- `data/production/knowledge/documents/` — static clinic knowledge for RAG
- `data/source_dataset/` — original synthetic dataset/reference JSON files
- `evaluation/` — RAG, multilingual agent, and E2E QA reports
- `tests/` — regression tests
- `storage/` — runtime SQLite/RAG state; SQLite DB is intentionally recreated locally

## Architecture

```text
User
  -> Streamlit UI
  -> AI Agent
      -> RAG (static clinic knowledge)
      -> Controlled Tools (live operational actions)
          -> Services / Repositories
          -> SQLite Database
  -> Response
```
