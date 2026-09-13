from pathlib import Path
import re
from .schemas import Document

class DocumentLoader:
    SUPPORTED = {'.md', '.txt'}
    def load(self, directory: str, clinic_id: str) -> list[Document]:
        docs=[]
        for path in sorted(Path(directory).glob('*')):
            if path.suffix.lower() not in self.SUPPORTED or not path.is_file(): continue
            raw=path.read_text(encoding='utf-8')
            text=re.sub(r'^#+\s*', '', raw, flags=re.MULTILINE)
            text=re.sub(r'\s+', ' ', text).strip()
            if not text: continue
            stem=path.stem
            parts=stem.split('_')
            # Filename conventions: <name>_<language> are not required; explicit defaults below.
            language='English'
            if stem.startswith('urdu_'): language='Urdu'
            elif stem.startswith('roman_'): language='Roman Urdu'
            elif stem.startswith('mixed_'): language='Mixed'
            # Prefer language markers in content for our synthetic KB.
            docs.append(Document(
                document_id=stem,
                text=text,
                metadata={'clinic_id':clinic_id,'document_type':stem if stem not in {'urdu_faq','roman_urdu_faq','mixed_faq'} else 'faq','source':path.name,'language':language}
            ))
        return docs
