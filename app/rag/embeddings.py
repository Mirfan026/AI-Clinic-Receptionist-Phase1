from typing import Sequence
import numpy as np

class EmbeddingProvider:
    def embed(self, texts: Sequence[str]) -> np.ndarray: raise NotImplementedError

class SentenceTransformerEmbeddings(EmbeddingProvider):
    def __init__(self, model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2'):
        from sentence_transformers import SentenceTransformer
        self.model=SentenceTransformer(model_name)
    def embed(self,texts):
        return np.asarray(self.model.encode(list(texts), normalize_embeddings=True),dtype=np.float32)

class TfidfMultilingualEmbeddings(EmbeddingProvider):
    """Offline deterministic fallback using word + character n-grams."""
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import FeatureUnion
        self.vectorizer=FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1, sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2,5), min_df=1, sublinear_tf=True)),
        ])
        self._fitted=False
    def fit(self,texts):
        self.vectorizer.fit(list(texts)); self._fitted=True; return self
    def embed(self,texts):
        if not self._fitted: self.fit(texts)
        x=self.vectorizer.transform(list(texts)).astype(np.float32).toarray()
        norms=np.linalg.norm(x,axis=1,keepdims=True); norms[norms==0]=1
        return x/norms

def build_embedding_provider(backend='auto', model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2'):
    if backend in {'sentence-transformers','auto'}:
        try: return SentenceTransformerEmbeddings(model_name)
        except Exception:
            if backend=='sentence-transformers': raise
    return TfidfMultilingualEmbeddings()
