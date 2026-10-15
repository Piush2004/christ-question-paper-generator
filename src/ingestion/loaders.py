"""Text extraction for PDF / DOCX / TXT (master-prompt A 9).

Page structure and the original extracted text are always preserved — nothing here normalizes or
discards content; that happens later in `src/preprocessing/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from typing import Any

from src.ingestion.exceptions import (
    DocumentLoadError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)

# A page is flagged as needing OCR if it has fewer than this many extractable characters,
# which is the standard heuristic for "this page is an image, not embedded text."
MIN_TEXT_CHARS_PER_PAGE = 20

@dataclass
class PageBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block_type: int

@dataclass
class PageTable:
    headers: list[str]
    rows: list[list[str]]

@dataclass
class Page:
    page_number: int  # 1-indexed
    text: str
    needs_ocr: bool = False
    tables: list[PageTable] = field(default_factory=list)
    blocks: list[PageBlock] = field(default_factory=list)


@dataclass
class DocumentText:
    source_path: Path
    pages: list[Page] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def pages_needing_ocr(self) -> list[int]:
        return [p.page_number for p in self.pages if p.needs_ocr]


def load_document(path: Path) -> DocumentText:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _load_pdf(path)
    if ext == ".docx":
        return _load_docx(path)
    if ext == ".txt":
        return _load_txt(path)
    raise UnsupportedFormatError(f"Unsupported extension for load_document: {ext}")


def _load_pdf(path: Path) -> DocumentText:
    pages: list[Page] = []
    try:
        with fitz.open(path) as doc:
            if doc.is_encrypted:
                raise EncryptedDocumentError(
                    f"{path} is password-protected. This pipeline has no password source; "
                    "decrypt the file externally before placing it in data/raw/."
                )
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text")
                needs_ocr = len(text.strip()) < MIN_TEXT_CHARS_PER_PAGE
                
                page_blocks = []
                for b in page.get_text("blocks"):
                    page_blocks.append(PageBlock(x0=b[0], y0=b[1], x1=b[2], y1=b[3], text=b[4], block_type=b[6]))
                
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
                
                pages.append(Page(page_number=i, text=text, needs_ocr=needs_ocr, tables=page_tables, blocks=page_blocks))
    except EncryptedDocumentError:
        raise
    except fitz.FileDataError as exc:
        raise DocumentLoadError(f"{path} could not be parsed as a PDF (corrupt or truncated): {exc}") from exc
    return DocumentText(source_path=path, pages=pages)


def _load_docx(path: Path) -> DocumentText:
    try:
        doc = DocxDocument(str(path))
    except PackageNotFoundError as exc:
        raise DocumentLoadError(f"{path} could not be parsed as a DOCX (corrupt or not a valid OOXML package): {exc}") from exc
    pages_text: list[list[str]] = [[]]
    for para in doc.paragraphs:
        pages_text[-1].append(para.text)
        for run in para.runs:
            if run._element.findall(
                ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
                "[@{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type='page']"
            ):
                pages_text.append([])
    pages = [
        Page(page_number=i, text="\n".join(lines), needs_ocr=False)
        for i, lines in enumerate(pages_text, start=1)
        if any(line.strip() for line in lines) or i == 1
    ]
    return DocumentText(source_path=path, pages=pages)


def _load_txt(path: Path) -> DocumentText:
    text = path.read_text(encoding="utf-8", errors="replace")
    return DocumentText(source_path=path, pages=[Page(page_number=1, text=text, needs_ocr=False)])
