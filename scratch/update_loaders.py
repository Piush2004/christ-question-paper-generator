import sys
from pathlib import Path
import re

file_path = Path('src/ingestion/loaders.py')
content = file_path.read_text('utf-8')

import_insert = '''import pymupdf as fitz
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError'''

new_imports = '''import pymupdf as fitz
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from typing import Any'''

content = content.replace(import_insert, new_imports)

page_def = '''@dataclass
class Page:
    page_number: int  # 1-indexed
    text: str
    needs_ocr: bool = False'''

new_page_def = '''@dataclass
class PageTable:
    headers: list[str]
    rows: list[list[str]]

@dataclass
class Page:
    page_number: int  # 1-indexed
    text: str
    needs_ocr: bool = False
    tables: list[PageTable] = field(default_factory=list)'''

content = content.replace(page_def, new_page_def)

load_pdf_old = '''            for i, page in enumerate(doc, start=1):
                text = page.get_text("text")
                needs_ocr = len(text.strip()) < MIN_TEXT_CHARS_PER_PAGE
                pages.append(Page(page_number=i, text=text, needs_ocr=needs_ocr))'''

load_pdf_new = '''            for i, page in enumerate(doc, start=1):
                text = page.get_text("text")
                needs_ocr = len(text.strip()) < MIN_TEXT_CHARS_PER_PAGE
                
                page_tables = []
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for tab in tabs.tables:
                        df = tab.to_pandas()
                        if df is not None and not df.empty:
                            headers = [str(c) for c in df.columns]
                            rows = []
                            for _, row in df.iterrows():
                                rows.append([str(x) if x is not None else "" for x in row.values])
                            page_tables.append(PageTable(headers=headers, rows=rows))
                
                pages.append(Page(page_number=i, text=text, needs_ocr=needs_ocr, tables=page_tables))'''

content = content.replace(load_pdf_old, load_pdf_new)

# write it back
file_path.write_text(content, 'utf-8')
print('Updated loaders.py')
