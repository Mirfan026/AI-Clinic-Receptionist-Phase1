from pathlib import Path
from app.rag.pipeline import RAGPipeline
from app.rag.config import RAGConfig

def make(tmp_path):
    root=Path(__file__).resolve().parents[1]
    return RAGPipeline(RAGConfig(chunk_size=300,chunk_overlap=50,top_k=5,similarity_threshold=.20,vector_store_path=str(tmp_path/'vs'),embedding_backend='tfidf'))

def test_ingest_and_metadata(tmp_path):
    p=make(tmp_path); root=Path(__file__).resolve().parents[1]
    out=p.ingest(root/'data/production/knowledge/documents','CLINIC-001')
    assert out['documents']>=12 and out['chunks']>=12
    r=p.retrieve('What are the clinic hours?','CLINIC-001')
    assert r.results
    for x in r.results:
        assert x.metadata['clinic_id']=='CLINIC-001'
        for k in ('document_type','source','language'): assert k in x.metadata

def test_metadata_filter(tmp_path):
    p=make(tmp_path); root=Path(__file__).resolve().parents[1]; p.ingest(root/'data/production/knowledge/documents','CLINIC-001')
    r=p.retrieve('payment card cash','CLINIC-001',document_type='payment_information')
    assert r.results and all(x.metadata['document_type']=='payment_information' for x in r.results)

def test_multilingual_queries(tmp_path):
    p=make(tmp_path); root=Path(__file__).resolve().parents[1]; p.ingest(root/'data/production/knowledge/documents','CLINIC-001')
    qs=['What are the clinic opening hours?','کلینک اتوار کو کھلا ہے؟','Clinic Sunday ko open hota hai?','Cardiology ki consultation fee کتنی ہے؟']
    assert all(p.retrieve(q,'CLINIC-001').results for q in qs)

def test_no_result_handling(tmp_path):
    p=make(tmp_path); root=Path(__file__).resolve().parents[1]; p.ingest(root/'data/production/knowledge/documents','CLINIC-001')
    p.config.__dict__ if False else None
    r=p.retrieve('Does the clinic have a helicopter landing pad?','CLINIC-001')
    assert r.no_results or r.results[0].score < .5
