# RAG Pipeline — AI Clinic Receptionist

Implements: Documents → Loading → Cleaning → Chunking → Metadata → Embeddings → Vector Store → Retrieval → Context → LLM Response.

## Design
- **Knowledge boundary:** RAG answers static clinic knowledge only. Live availability is never read from RAG; it belongs to `check_availability()`.
- **Metadata:** every chunk contains `clinic_id`, `document_type`, `source`, `language`, plus `chunk_index`.
- **Vector store:** ChromaDB is the preferred production backend. If ChromaDB is unavailable in the runtime, the package falls back to a small persistent NumPy cosine index so tests remain runnable offline.
- **Embeddings:** `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` when available; deterministic character n-gram TF-IDF fallback for offline testing.
- **Retrieval:** configurable top-k, metadata filters and similarity threshold.
- **Grounding:** response prompt explicitly prohibits outside knowledge/hallucination; no-result responses say the information is unavailable. A deterministic extractive answerer is used in tests so evaluation does not depend on an external LLM.

## Run
```bash
python scripts/build_knowledge_index.py
python scripts/run_rag_evaluation.py
pytest -q
```

Environment variables:
`RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `VECTOR_STORE_PATH`, `RAG_COLLECTION_NAME`, `EMBEDDING_BACKEND`.

## Production LLM stage
Use `grounded_prompt()` as the only context passed to the answer model. The model must be instructed to abstain when context is empty or insufficient. Do not pass unrestricted web/database context into this stage. For availability, route to the structured tool instead.
