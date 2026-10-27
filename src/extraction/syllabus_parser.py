"""Parser for the real CHRIST BCA syllabus documents in `Question Papers/BCA/`.

These documents are the authoritative source of the Course Outcome text that already appears
verbatim in the real exam papers (see docs/VALIDITY_AUDIT.md §Q2/§Q3) and of each course's
syllabus units — used to ground topic clustering in `src/generation/topics.py` instead of relying
purely on unsupervised clusters of past questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import docx
import pymupdf


@dataclass
class SyllabusUnit:
    number: int
    title: str
    topics: str
    teaching_hours: int | None


_CO_LINE = re.compile(r"^co\s*(\d+)\s*:\s*(.+)$", re.IGNORECASE)
_UNIT_HEADING = re.compile(r"^unit[\s-]*(\d+)\b", re.IGNORECASE)
_TEACHING_HOURS = re.compile(r"teaching\s*hours?\s*:?\s*(\d+)", re.IGNORECASE)
_UNIT_STOP_PREFIXES = (
    "text books", "essential reading", "reference", "web resources",
    "lab exercises", "course objectives", "co – po mapping", "co - po mapping",
)


def extract_course_outcomes(section_lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in section_lines:
        m = _CO_LINE.match(line.strip())
        if m:
            out[f"CO{m.group(1)}"] = m.group(2).strip()
    return out


def extract_units(section_lines: list[str]) -> list[SyllabusUnit]:
    units: list[SyllabusUnit] = []
    i, n = 0, len(section_lines)
    while i < n:
        m = _UNIT_HEADING.match(section_lines[i].strip())
        if not m:
            i += 1
            continue
        number = int(m.group(1))
        hm = _TEACHING_HOURS.search(section_lines[i])
        teaching_hours = int(hm.group(1)) if hm else None
        i += 1
        while i < n and not section_lines[i].strip():
            i += 1
        title = section_lines[i].strip() if i < n else ""
        i += 1
        topics_parts: list[str] = []
        while i < n:
            line = section_lines[i].strip()
            if _UNIT_HEADING.match(line) or any(line.lower().startswith(p) for p in _UNIT_STOP_PREFIXES):
                break
            if line:
                topics_parts.append(line)
            i += 1
        units.append(SyllabusUnit(number, title, ". ".join(topics_parts), teaching_hours))
    return units


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


@dataclass
class SyllabusCourse:
    code: str
    title: str
    source_file: str
    course_outcomes: dict[str, str]
    units: list[SyllabusUnit]


def parse_syllabus_file(path: Path) -> list[SyllabusCourse]:
    lines = _flatten_pdf(path) if path.suffix.lower() == ".pdf" else _flatten_docx(path)
    courses = []
    for code, title, section_lines in split_into_course_sections(lines):
        course_outcomes = extract_course_outcomes(section_lines)
        units = extract_units(section_lines)
        if not course_outcomes and not units:
            continue  # heading-like false positive, not a real course section — never fabricate
        courses.append(SyllabusCourse(code, title, path.name, course_outcomes, units))
    return courses


def _flatten_docx(path: Path) -> list[str]:
    doc = docx.Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def _flatten_pdf(path: Path) -> list[str]:
    doc = pymupdf.open(path, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return [line.strip() for line in text.split("\n") if line.strip()]
