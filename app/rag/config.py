from dataclasses import dataclass
import os

@dataclass(frozen=True)
class RAGConfig:
    chunk_size: int = 700
    chunk_overlap: int = 100
    top_k: int = 5
    similarity_threshold: float = 0.30
    vector_store_path: str = './storage/rag_vector_store'
    collection_name: str = 'clinic_knowledge'
    embedding_backend: str = 'auto'

    @classmethod
    def from_env(cls):
        return cls(
            chunk_size=int(os.getenv('RAG_CHUNK_SIZE', '700')),
            chunk_overlap=int(os.getenv('RAG_CHUNK_OVERLAP', '100')),
            top_k=int(os.getenv('RAG_TOP_K', '5')),
            similarity_threshold=float(os.getenv('RAG_SIMILARITY_THRESHOLD', '0.30')),
            vector_store_path=os.getenv('VECTOR_STORE_PATH', './storage/rag_vector_store'),
            collection_name=os.getenv('RAG_COLLECTION_NAME', 'clinic_knowledge'),
            embedding_backend=os.getenv('EMBEDDING_BACKEND', 'auto'),
        )

    def validate(self):
        if self.chunk_size <= 0: raise ValueError('chunk_size must be > 0')
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size: raise ValueError('chunk_overlap must be >=0 and < chunk_size')
        if not 1 <= self.top_k <= 100: raise ValueError('top_k must be 1..100')
        if not 0 <= self.similarity_threshold <= 1: raise ValueError('similarity_threshold must be 0..1')
