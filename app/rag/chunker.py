from .schemas import Document, Chunk
from .cleaner import clean_text

class TextChunker:
    def __init__(self, chunk_size: int=700, overlap: int=100):
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size: raise ValueError('Invalid chunk configuration')
        self.chunk_size=chunk_size; self.overlap=overlap
    def chunk(self, doc: Document) -> list[Chunk]:
        text=clean_text(doc.text)
        chunks=[]; start=0; i=0
        while start < len(text):
            end=min(len(text), start+self.chunk_size)
            if end < len(text):
                boundary=max(text.rfind('. ',start,end), text.rfind('۔ ',start,end), text.rfind('\n',start,end))
                if boundary > start + self.chunk_size//2: end=boundary+1
            piece=text[start:end].strip()
            if piece:
                md=dict(doc.metadata); md['chunk_index']=i
                chunks.append(Chunk(f'{doc.document_id}:{i}',piece,md)); i+=1
            if end >= len(text): break
            start=max(end-self.overlap, start+1)
        return chunks
