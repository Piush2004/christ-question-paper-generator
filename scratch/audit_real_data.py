import sys
from pathlib import Path
from src.ingestion.loaders import load_document
from src.extraction.engine import QuestionExtractor

doc_table = load_document(Path('data/raw/BCA431 2024.pdf'))
qs_table = QuestionExtractor().extract(doc_table)

doc_text = load_document(Path('data/raw/cn2024.pdf'))
qs_text = QuestionExtractor().extract(doc_text)

print('--- TABLE BASED (BCA431) ---')
for i, q in enumerate(qs_table[:15]):
    print(f'[{i}] Q.No: {q.question_number_raw}, Sec: {q.section_label}, Marks: {q.marks}')
    print(f'     CO: {q.course_outcome}, RBT: {q.bloom}, Alt: {q.is_alternative}')
    text_safe = q.raw_text.encode('ascii', 'ignore').decode('ascii')
    print(f'     Text: {repr(text_safe[:80])}')
    
print('\n--- TEXT BASED (CN2024) ---')
for i, q in enumerate(qs_text[:10]):
    print(f'[{i}] Q.No: {q.question_number_raw}, Sec: {q.section_label}, Marks: {q.marks}')
    print(f'     CO: {q.course_outcome}, RBT: {q.bloom}, Alt: {q.is_alternative}')
    text_safe = q.raw_text.encode('ascii', 'ignore').decode('ascii')
    print(f'     Text: {repr(text_safe[:80])}')
