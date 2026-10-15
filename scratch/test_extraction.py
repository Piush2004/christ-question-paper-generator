import sys
from pathlib import Path
from src.ingestion.loaders import load_document
from src.extraction.engine import QuestionExtractor

pdf_path = Path('data/raw/BCA431 2024.pdf')
doc = load_document(pdf_path)
extractor = QuestionExtractor()
qs = extractor.extract(doc)

for q in qs[:5]:
    print(f'Num: {q.question_number_raw}, Sec: {q.section_label}, Marks: {q.marks}')
    print(f'Text: {repr(q.raw_text[:60])}...')

print('---')
pdf2 = Path('data/raw/cn2024.pdf')
doc2 = load_document(pdf2)
qs2 = extractor.extract(doc2)
for q in qs2[:5]:
    print(f'Num: {q.question_number_raw}, Sec: {q.section_label}, Marks: {q.marks}')
    print(f'Text: {repr(q.raw_text[:60])}...')
