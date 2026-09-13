from dataclasses import dataclass, asdict
from typing import Any, Optional

@dataclass(frozen=True)
class Document:
    document_id: str
    text: str
    metadata: dict[str, Any]

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]

@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]

@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    results: list[RetrievalResult]
    no_results: bool
    reason: Optional[str] = None
