"""Build or refresh the clinic knowledge vector index.

Rebuilds only when the corpus, chunking configuration or embedding backend has
changed. Pass --force to rebuild unconditionally.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.config import RAGConfig
from app.rag.pipeline import RAGPipeline

if __name__ == '__main__':
    documents = ROOT / 'data/production/knowledge/documents'
    pipeline = RAGPipeline(RAGConfig.from_env())

    if '--force' in sys.argv:
        print({'rebuilt': True, **pipeline.ingest(documents, 'CLINIC-001')})
    else:
        result = pipeline.ensure_index(documents, 'CLINIC-001')
        print(result)
        if not result['rebuilt']:
            print('Index already matches the corpus. Use --force to rebuild anyway.')
