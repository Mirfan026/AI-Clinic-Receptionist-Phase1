import re
from .schemas import RetrievalResponse
from .lexicon import EXTRA_STOPWORDS, EXTRA_SYNONYMS

_STOP=set('a an the is are am to of for in on at do does did what which how can could would should you your we our i me my please tell give have has had this that and or with from about'.split())
_STOP |= EXTRA_STOPWORDS
_SYNONYMS={
    'opening':'timings','open':'timings','hours':'timings','hour':'timings','close':'timings','closing':'timings',
    'fee':'fees','cost':'fees','price':'fees','charge':'fees',
    'doctor':'doctors','specialist':'specializes','specialized':'specializes',
    'phone':'contact','number':'contact','email':'contact',
    'cancel':'cancellation','cancelling':'cancellation','reschedule':'rescheduling','rescheduled':'rescheduling',
    'opening':'timings','open':'timings','offer':'services','offers':'services','provide':'services','provides':'services',
    'pay':'payment','paid':'payment','accept':'accepted','methods':'payment',
    'اوقات':'timings','کلینک':'clinic','کیا':'what','ہیں؟':'is','کے':'of','ke':'of',
}
# Shared Roman Urdu / Urdu vocabulary. Existing entries win on conflict so the
# retriever's established behaviour is never silently altered.
_SYNONYMS={**EXTRA_SYNONYMS, **_SYNONYMS}

# Arabic-script punctuation falls inside the \u0600-\u06ff block, so it sticks to
# the preceding word and stops it matching its own stop-word entry.
_PUNCT='؟۔،؛٫٬!?.,:;'

def _tokens(text):
    toks=[]
    for t in re.findall(r'[\w\u0600-\u06ff]+', text.lower()):
        t=t.strip(_PUNCT)
        if not t or t in _STOP: continue
        toks.append(_SYNONYMS.get(t,t))
    return set(toks)


class Retriever:
    def __init__(self,vector_store,embedder,top_k=5,similarity_threshold=.30):
        self.store=vector_store; self.embedder=embedder; self.top_k=top_k; self.threshold=similarity_threshold
    def retrieve(self,query,metadata_filter=None):
        q=self.embedder.embed([query])[0]
        # Re-ranking can only reorder what the store returns. A pool of 10 starved
        # the lexical stage: for a cross-lingual query every English chunk scores
        # ~0 semantically, so the pool was effectively arbitrary and the right
        # document could be truncated before it was ever scored. Widen the pool
        # and let the blended score decide. Thresholds are unchanged.
        raw=self.store.query(q,max(self.top_k*10,50),metadata_filter)
        qt=_tokens(query)
        rescored=[]
        for r in raw:
            dt=_tokens(r.text)
            overlap=len(qt & dt)
            lexical=(overlap/max(1,len(qt)))
            source_tokens=_tokens(str(r.metadata.get("source", ""))) | _tokens(str(r.metadata.get("document_type", "")))
            source_overlap=len(qt & source_tokens)
            source_lexical=source_overlap/max(1,len(qt))
            # Blend semantic and body lexical evidence. The source/type signal was
            # previously computed and discarded; it is now a bounded tie-breaker so
            # that "cancellation policy" prefers cancellation_policy.md over a generic
            # FAQ chunk, without letting a filename outrank real content.
            score=min(1.0, 0.65*r.score + 0.35*lexical)
            rescored.append((source_lexical, type(r)(r.chunk_id,r.text,score,r.metadata)))
        rescored.sort(key=lambda x:(round(x[1].score,3), x[0]),reverse=True)
        rescored=[r for _,r in rescored]
        results=[r for r in rescored[:self.top_k] if r.score >= self.threshold]
        # Strong abstention rule: if no meaningful query token occurs in a candidate,
        # do not let a generic semantic similarity pass the threshold.
        if qt:
            meaningful=[r for r in results if len(qt & _tokens(r.text))>0]
            results=meaningful
        return RetrievalResponse(query,results,not bool(results),'No knowledge-base chunks met the similarity threshold.' if not results else None)
