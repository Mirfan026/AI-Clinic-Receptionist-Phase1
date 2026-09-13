import re

from .lexicon import EXTRA_STOPWORDS, EXTRA_SYNONYMS

STOP=set('a an the is are am to of for in on at do does did what which how can could would should you your we our i me my please tell give have has had this that and or with from about by clinic maple crescent family information provide provides offering offer ke kya hain ہے ہیں کیا کے کیا؟ ہیں؟'.split())
STOP |= EXTRA_STOPWORDS
SYN={'opening':'timings','open':'timings','hours':'timings','hour':'timings','close':'timings','closing':'timings','fee':'fees','cost':'fees','price':'fees','charge':'fees','doctor':'doctors','specialist':'specializes','specialized':'specializes','phone':'contact','number':'contact','email':'contact','cancel':'cancellation','cancelling':'cancellation','reschedule':'rescheduling','rescheduled':'rescheduling','methods':'payment','method':'payment','accept':'accepted','offer':'services','offers':'services','provide':'services','provides':'services','pay':'payment','paid':'payment','methods':'payment',
'اوقات':'timings','اوقاتِ':'timings','کھلا':'open','کھلی':'open','بند':'closed','ادائیگی':'payment','نقد':'cash','کارڈ':'card','فیس':'fees','ڈاکٹر':'doctors','سروس':'services','سروسز':'services','پتہ':'address','فون':'contact','رابطہ':'contact','کلینک':'clinic'}
# Shared Roman Urdu / Urdu vocabulary; existing entries win on conflict.
SYN={**EXTRA_SYNONYMS, **SYN}

def _tokens(text):
    out=[]
    for t in re.findall(r'[\w\u0600-\u06ff]+',text.lower()):
        if t in STOP: continue
        out.append(SYN.get(t,t))
    return set(out)

def grounded_prompt(question: str, context: str) -> str:
    return f"""You are the clinic knowledge assistant. Answer ONLY from the supplied knowledge-base context. Do not use outside knowledge. If the context does not contain the answer, say that the information is unavailable in the clinic knowledge base. Never invent clinic facts, prices, policies, doctor details, facilities, or availability. Live appointment availability must be obtained from the structured availability tool, not RAG.\n\nKNOWLEDGE BASE CONTEXT:\n{context or '[NO RELEVANT KNOWLEDGE FOUND]'}\n\nUSER QUESTION:\n{question}\n\nANSWER:"""

def extractive_answer(question, context):
    """Deterministic grounded answerer; returns only text present in retrieved context."""
    unavailable='The information is unavailable in the clinic knowledge base.'
    if not context: return unavailable
    q=_tokens(question)
    if not q: return unavailable
    blocks=context.split('\n\n')
    candidates=[]
    represented=set()
    for block in blocks:
        lines=block.splitlines()
        header=lines[0] if lines else ''
        text=' '.join(lines[1:]) if len(lines)>1 else block
        source_tokens=_tokens(header.replace('_',' ').replace('.md',''))
        for sentence in re.split(r'(?<=[.!؟۔])\s+', text):
            toks=_tokens(sentence)
            overlap=len(q & toks)
            if overlap:
                # Prefer sentences from a source whose metadata matches the question.
                source_overlap=len(q & source_tokens)
                score=overlap/max(1,len(q)) + 0.35*(source_overlap/max(1,len(q)))
                candidates.append((score, overlap, sentence))
                represented |= (q & toks)
    coverage=len(represented)/len(q)
    # Do not answer from generic clinic/service language when a specific requested
    # facility/entity (e.g. pharmacy, parking, insurance) is absent from context.
    specific_q={t for t in q if t not in {'timings','services','payment','contact','doctors','open','closed','address','cash','card'}}
    specific_present={t for t in specific_q if any(t in _tokens(s) for s in [c[2] for c in candidates])}
    if specific_q and len(specific_present) < len(specific_q):
        return unavailable
    if coverage < 0.75:
        return unavailable
    candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
    # Stay within the strongest source. This prevents a correct FAQ answer from
    # being polluted by a loosely related policy sentence (e.g. clinic hours +
    # human-support hours).
    best_source = None
    if candidates:
        # Reconstruct source identity from the context block containing the sentence.
        for block in blocks:
            if candidates[0][2] in block:
                best_source = block.splitlines()[0] if block.splitlines() else ''
                break
    out=[]
    for _,_,sentence in candidates:
        if best_source and best_source not in next((b for b in blocks if sentence in b), ''):
            continue
        if sentence not in out:
            out.append(sentence)
        if len(out)==2: break
    return ' '.join(out) if out else unavailable
