"""Parser for the real CHRIST BCA syllabus documents in `Question Papers/BCA/`.

These documents are the authoritative source of the Course Outcome text that already appears
verbatim in the real exam papers (see docs/VALIDITY_AUDIT.md §Q2/§Q3) and of each course's
syllabus units — used to ground topic clustering in `src/generation/topics.py` instead of relying
purely on unsupervised clusters of past questions.
"""

from __future__ import annotations

from pathlib import Path

import docx
import pymupdf


def _flatten_docx(path: Path) -> list[str]:
    doc = docx.Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def _flatten_pdf(path: Path) -> list[str]:
    doc = pymupdf.open(path, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return [line.strip() for line in text.split("\n") if line.strip()]
