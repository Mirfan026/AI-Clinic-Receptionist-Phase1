from pathlib import Path
import json

import numpy as np

from .schemas import Chunk, RetrievalResult


class VectorStore:
    def add(self, chunks, embeddings):
        raise NotImplementedError

    def query(self, embedding, top_k, metadata_filter=None):
        raise NotImplementedError


class NumpyVectorStore(VectorStore):
    """Small local persistent vector index used when ChromaDB is unavailable."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.file = self.path / "index.json"
        self.items = []

        if self.file.exists():
            self.items = json.loads(
                self.file.read_text(encoding="utf-8")
            )

    def add(self, chunks, embeddings):
        for chunk, embedding in zip(chunks, embeddings):
            self.items = [
                item
                for item in self.items
                if item["id"] != chunk.chunk_id
            ]

            self.items.append(
                {
                    "id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                    "embedding": embedding.tolist(),
                }
            )

        self._save()

    def _save(self):
        self.file.write_text(
            json.dumps(self.items, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _match(metadata, metadata_filter):
        if not metadata_filter:
            return True

        return all(
            metadata.get(key) == value
            for key, value in metadata_filter.items()
        )

    def query(self, embedding, top_k, metadata_filter=None):
        query_vector = np.asarray(
            embedding,
            dtype=np.float32,
        )

        query_norm = np.linalg.norm(query_vector) or 1.0

        scored = []

        for item in self.items:
            if not self._match(
                item["metadata"],
                metadata_filter,
            ):
                continue

            item_vector = np.asarray(
                item["embedding"],
                dtype=np.float32,
            )

            item_norm = np.linalg.norm(item_vector) or 1.0

            score = float(
                np.dot(query_vector, item_vector)
                / (query_norm * item_norm)
            )

            scored.append(
                RetrievalResult(
                    item["id"],
                    item["text"],
                    score,
                    item["metadata"],
                )
            )

        return sorted(
            scored,
            key=lambda result: result.score,
            reverse=True,
        )[:top_k]


class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        path,
        collection_name="clinic_knowledge",
    ):
        import chromadb

        self.client = chromadb.PersistentClient(
            path=str(path)
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        )

    def add(self, chunks, embeddings):
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=[
                embedding.tolist()
                for embedding in embeddings
            ],
        )

    def query(
        self,
        embedding,
        top_k,
        metadata_filter=None,
    ):
        # Build a valid Chroma metadata filter.
        #
        # For multiple fields:
        # {
        #     "$and": [
        #         {"clinic_id": {"$eq": "CLINIC-001"}},
        #         {"document_type": {"$eq": "payment_information"}}
        #     ]
        # }
        #
        # The important point is that `key` below is the actual
        # metadata field name. Do NOT use the literal string "k".

        if not metadata_filter:
            where = None

        elif len(metadata_filter) > 1:
            where = {
                "$and": [
                    {
                        key: {
                            "$eq": value
                        }
                    }
                    for key, value in metadata_filter.items()
                ]
            }

        else:
            key, value = next(
                iter(metadata_filter.items())
            )

            where = {
                key: {
                    "$eq": value
                }
            }

        out = self.collection.query(
            query_embeddings=[
                embedding.tolist()
            ],
            n_results=top_k,
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        results = []

        for index, distance in enumerate(
            out["distances"][0]
        ):
            results.append(
                RetrievalResult(
                    out["ids"][0][index],
                    out["documents"][0][index],
                    float(1 - distance),
                    out["metadatas"][0][index],
                )
            )

        return results


def build_vector_store(
    path,
    collection_name="clinic_knowledge",
):
    try:
        return ChromaVectorStore(
            path,
            collection_name,
        )
    except Exception:
        return NumpyVectorStore(path)