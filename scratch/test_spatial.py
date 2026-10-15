
from pathlib import Path
from src.ingestion.loaders import load_document
from src.extraction.engine import QuestionExtractor
import re

doc = load_document(Path('data/raw/cn2024.pdf'))
lines = QuestionExtractor()._flatten_lines(doc)
markers = QuestionExtractor()._classify_lines(lines)

sections = []
for m in markers:
    if m.level == 'section':
        # Find all lines on the same page with the same y0 (same block)
        block_lines = [l.text for l in lines if l.page_number == m.page_number and abs(l.y0 - m.y0) < 1.0]
        block_text = '\\n'.join(block_lines)
        print('Section:', m.number, 'Block text:', repr(block_text))
