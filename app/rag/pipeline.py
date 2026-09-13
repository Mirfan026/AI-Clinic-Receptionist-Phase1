from .config import RAGConfig
from .loader import DocumentLoader
from .chunker import TextChunker
from .cleaner import clean_text
from .embeddings import build_embedding_provider
from .vector_store import build_vector_store
from .retriever import Retriever
from .context import build_context
from .grounding import grounded_prompt, extractive_answer

# Must match grounding.extractive_answer's abstention string exactly.
UNAVAILABLE_TEXT = 'The information is unavailable in the clinic knowledge base.'

class RAGPipeline:
    def __init__(self,config=None):
        self.config=config or RAGConfig.from_env(); self.config.validate()
        self.embedder=build_embedding_provider(self.config.embedding_backend)
        self.store=build_vector_store(self.config.vector_store_path,self.config.collection_name)
        # TF-IDF is an offline fallback; its vocabulary must be reconstructed from the
        # persisted corpus when a new process starts, otherwise query/document vectors
        # can have different dimensions.
        if hasattr(self.embedder, 'fit') and hasattr(self.store, 'items') and self.store.items:
            self.embedder.fit([x['text'] for x in self.store.items])
        self.retriever=Retriever(self.store,self.embedder,self.config.top_k,self.config.similarity_threshold)
    def ingest(self,documents_dir,clinic_id):
        docs=DocumentLoader().load(documents_dir,clinic_id)
        chunks=[]
        for d in docs:
            d2=type(d)(d.document_id,clean_text(d.text),d.metadata)
            chunks.extend(TextChunker(self.config.chunk_size,self.config.chunk_overlap).chunk(d2))
        texts=[c.text for c in chunks]
        if hasattr(self.embedder,'fit'): self.embedder.fit(texts)
        embs=self.embedder.embed(texts)
        self.store.add(chunks,embs)
        return {'documents':len(docs),'chunks':len(chunks)}
    def ensure_index(self,documents_dir,clinic_id):
        """Ingest only when the persisted index no longer matches the corpus.

        A stale index is worse than no index: it answers confidently from
        documents that have since changed. The fingerprint covers the chunking
        configuration, the embedding backend, the vector store implementation
        and every source file's size and modification time, so any of those
        changing triggers a rebuild instead of silent wrong retrieval.
        """
        from hashlib import sha256
        from pathlib import Path
        import json

        directory=Path(documents_dir)
        parts=[
            f"chunk={self.config.chunk_size}:{self.config.chunk_overlap}",
            f"embedder={type(self.embedder).__name__}",
            f"store={type(self.store).__name__}",
            f"clinic={clinic_id}",
        ]
        for path in sorted(directory.glob('*')):
            if path.suffix.lower() in DocumentLoader.SUPPORTED and path.is_file():
                stat=path.stat()
                parts.append(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}")
        fingerprint=sha256("|".join(parts).encode("utf-8")).hexdigest()

        manifest=Path(self.config.vector_store_path)/'index_manifest.json'
        try:
            current=json.loads(manifest.read_text(encoding='utf-8')).get('fingerprint')
        except Exception:
            current=None

        if current == fingerprint:
            return {'rebuilt':False,'fingerprint':fingerprint}

        result=self.ingest(directory,clinic_id)
        manifest.parent.mkdir(parents=True,exist_ok=True)
        manifest.write_text(
            json.dumps({'fingerprint':fingerprint,**result},indent=2),
            encoding='utf-8',
        )
        return {'rebuilt':True,'fingerprint':fingerprint,**result}

    def _base_filter(self,clinic_id,document_type=None):
        base={'clinic_id':clinic_id}
        if document_type: base['document_type']=document_type
        return base

    def retrieve(self,query,clinic_id,document_type=None,language=None):
        base=self._base_filter(clinic_id,document_type)
        if language:
            # Prefer the user's language, but do not make language a hard availability
            # constraint: the KB may legitimately contain only English source material
            # for a supported administrative fact. Fall back to the clinic-wide corpus.
            preferred=dict(base); preferred['language']=language
            result=self.retriever.retrieve(query,preferred)
            if result.results:
                return result
        return self.retriever.retrieve(query,base)

    def answer(self,query,clinic_id,document_type=None,language=None):
        rr=self.retrieve(query,clinic_id,document_type,language)
        ctx=build_context(rr)
        text=extractive_answer(query,ctx)
        # The language-preferred pass returns as soon as it finds *any* chunk in
        # the user's language. With dense multilingual embeddings a Roman Urdu
        # question matches the Roman Urdu FAQ strongly enough to satisfy that
        # filter even when the FAQ does not contain the fact asked for - so the
        # clinic-wide corpus, which does contain it, was never searched.
        #
        # Retrying only when the first pass abstained is strictly additive: it
        # can turn an abstention into a grounded answer, never the reverse, and
        # the clinic-wide result passes through the same grounding gate. If both
        # passes abstain, the system still abstains.
        if language and text == UNAVAILABLE_TEXT:
            wide=self.retriever.retrieve(query,self._base_filter(clinic_id,document_type))
            wide_ctx=build_context(wide)
            wide_text=extractive_answer(query,wide_ctx)
            # Adopt the wider pass even when it also abstains: it searched the
            # whole corpus, so its results are the honest record of what was
            # considered. Reporting a same-language chunk that could not answer
            # would misattribute the abstention to the wrong document.
            if wide.results:
                rr,ctx,text=wide,wide_ctx,wide_text
        return {'answer':text,'retrieval':rr,'context':ctx,'prompt':grounded_prompt(query,ctx)}