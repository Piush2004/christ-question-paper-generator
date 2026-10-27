"""Parser for the real CHRIST BCA syllabus documents in `Question Papers/BCA/`.

These documents are the authoritative source of the Course Outcome text that already appears
verbatim in the real exam papers (see docs/VALIDITY_AUDIT.md §Q2/§Q3) and of each course's
syllabus units — used to ground topic clustering in `src/generation/topics.py` instead of relying
purely on unsupervised clusters of past questions.
"""

from __future__ import annotations

import re
from pathlib import Path

import docx
import pymupdf

_HEADING = re.compile(
    r"^(?P<b>B?)CA\s?(?P<num>\d{2,3}[A-Za-z]?(?:-[A-Za-z0-9]+)?)"
    r"(?:\s*[-–:]\s*|\s+)"
    r"(?P<title>.+)$"
)


def _is_course_heading(line: str) -> tuple[str, str] | None:
    m = _HEADING.match(line.strip())
    if not m:
        return None
    title = m.group("title").strip()
    if not title:
        return None
    return "BCA" + m.group("num"), title


def split_into_course_sections(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    sections: list[tuple[str, str, list[str]]] = []
    current: list[str] | None = None
    for line in lines:
        heading = _is_course_heading(line)
        if heading:
            code, title = heading
            current = []
            sections.append((code, title, current))
            continue
        if current is not None:
            current.append(line)
    return sections


def _flatten_docx(path: Path) -> list[str]:
    doc = docx.Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def _flatten_pdf(path: Path) -> list[str]:
    doc = pymupdf.open(path, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return [line.strip() for line in text.split("\n") if line.strip()]
