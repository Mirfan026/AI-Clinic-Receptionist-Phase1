from .schemas import RetrievalResponse
from app.agent.safety import sanitize_retrieved_text

def build_context(response: RetrievalResponse, max_chars=6000) -> str:
    if response.no_results: return ''
    parts=[]; used=0
    for r in response.results:
        safe_text=sanitize_retrieved_text(r.text)
        block=f"[Source: {r.metadata.get('source')} | Type: {r.metadata.get('document_type')} | Language: {r.metadata.get('language')} | Score: {r.score:.3f}]\n{safe_text}"
        if used+len(block)>max_chars: break
        parts.append(block); used+=len(block)
    return '\n\n'.join(parts)
