from pathlib import Path
import csv, json, statistics, sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.pipeline import RAGPipeline
from app.rag.config import RAGConfig

def main():
    root=Path(__file__).resolve().parents[1]
    cfg=RAGConfig(chunk_size=700,chunk_overlap=100,top_k=5,similarity_threshold=.20,vector_store_path=str(root/'storage/rag_eval_index'),embedding_backend='auto')
    p=RAGPipeline(cfg); ing=p.ingest(root/'data/production/knowledge/documents','CLINIC-001')
    rows=list(csv.DictReader((root/'data/evaluation/rag_eval.csv').open(encoding='utf-8')))
    details=[]; answerable=[]; unanswerable=[]; lang_stats={}
    for r in rows:
        out=p.answer(r['question'],'CLINIC-001')
        got=bool(out['retrieval'].results)
        top_source=out['retrieval'].results[0].metadata.get('source') if got else None
        if r['expected_source']=='UNAVAILABLE':
            correct=('unavailable in the clinic knowledge base' in out['answer'].lower())
            unanswerable.append(correct)
        else:
            aliases={'clinic_timings':['clinic_timings.md','urdu_faq.md','roman_urdu_faq.md','mixed_faq.md'],'payment_information':['payment_information.md','urdu_faq.md','roman_urdu_faq.md','mixed_faq.md'],'doctors':['doctors.md','urdu_faq.md'],'services':['services.md','urdu_faq.md','roman_urdu_faq.md'],'faq':['faq.md','urdu_faq.md','roman_urdu_faq.md','mixed_faq.md'],'contact_information':['contact_information.md','urdu_faq.md'],'cancellation_policy':['cancellation_policy.md'],'rescheduling_policy':['rescheduling_policy.md'],'emergency_safety_policy':['emergency_safety_policy.md'],'human_support_policy':['human_support_policy.md']}
            hit=any(x.metadata.get('source') in aliases.get(r['expected_source'],[]) for x in out['retrieval'].results)
            correct=hit
            answerable.append(hit)
        lang_stats.setdefault(r['language'], {'total':0,'correct':0})
        lang_stats[r['language']]['total'] += 1
        if correct: lang_stats[r['language']]['correct'] += 1
        details.append({'id':r['id'],'question':r['question'],'expected':r['expected_source'],'retrieved':top_source,'scores':[round(x.score,3) for x in out['retrieval'].results],'correct':correct,'answer':out['answer']})
    report={'ingestion':ing,'config':{'chunk_size':700,'overlap':100,'top_k':5,'threshold':.20},'answerable_source_hit_rate':sum(answerable)/len(answerable),'unanswerable_rejection_rate':sum(unanswerable)/len(unanswerable),'overall_routing_retrieval_accuracy':sum(d['correct'] for d in details)/len(details),'language_accuracy':{k:round(v['correct']/v['total'],3) for k,v in lang_stats.items()},'details':details}
    (root/'evaluation').mkdir(exist_ok=True)
    (root/'evaluation/rag_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='details'},indent=2,ensure_ascii=False))
    return report
if __name__=='__main__': main()
