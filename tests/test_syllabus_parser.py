"""Parser for the real CHRIST BCA syllabus documents in `Question Papers/BCA/`."""
from pathlib import Path

import pytest

from src.extraction.syllabus_parser import _flatten_docx, _flatten_pdf

ROOT = Path(__file__).resolve().parents[1]
SYLLABUS_DIR = ROOT / "Question Papers" / "BCA"
pytestmark = pytest.mark.skipif(not SYLLABUS_DIR.exists(), reason="syllabus files not present")


def test_flatten_docx_contains_known_lines():
    lines = _flatten_docx(SYLLABUS_DIR / "BCA (2024-25) PS_Final_2nd year.docx")
    assert len(lines) > 500
    assert "Course Outcomes" in lines
    assert any(l.startswith("CO1: Demonstrate an understanding of the basic working process") for l in lines)


def test_flatten_pdf_contains_known_lines():
    lines = _flatten_pdf(SYLLABUS_DIR / "BCA(2025-26) PS-Final_1st year.pdf")
    assert len(lines) > 200
    assert any(l.strip() == "Course Outcome" for l in lines)
    assert any(l.startswith("CO1: Infer on the step for problem solving") for l in lines)


HEADING_FIXTURES = [
    ("BCA101-1 - FOUNDATIONAL MATHEMATICS", ("BCA101-1", "FOUNDATIONAL MATHEMATICS")),
    ("BCA 205-1 - PRINCIPLES OF SOFTWARE DEVELOPMENT – 1", ("BCA205-1", "PRINCIPLES OF SOFTWARE DEVELOPMENT – 1")),
    ("BCA 202-1 – INTRODUCTION TO WEB TECHNOLOGY", ("BCA202-1", "INTRODUCTION TO WEB TECHNOLOGY")),
    ("BCA104-2 - BASIC DISCRETE MATHEMATICS", ("BCA104-2", "BASIC DISCRETE MATHEMATICS")),
    ("BCA 108-3 OPERATING SYSTEM", ("BCA108-3", "OPERATING SYSTEM")),
    ("BCA310-3: MOBILE APPLICATIONS", ("BCA310-3", "MOBILE APPLICATIONS")),
    ("BCA212-4  DOT NET", ("BCA212-4", "DOT NET")),
    ("CA314-4– INTERNET OF THINGS", ("BCA314-4", "INTERNET OF THINGS")),  # missing leading "B" must be normalized back in
    ("Total Teaching Hours for Semester: 45", None),   # must NOT be mistaken for a heading
    ("CO1: Demonstrate an understanding of the basic working process of an operating system.", None),
]


@pytest.mark.parametrize("line,expected", HEADING_FIXTURES)
def test_is_course_heading(line, expected):
    from src.extraction.syllabus_parser import _is_course_heading
    assert _is_course_heading(line) == expected


def test_split_into_course_sections_splits_on_headings():
    from src.extraction.syllabus_parser import split_into_course_sections
    lines = ["intro junk", "BCA108-3 OPERATING SYSTEM", "Course Outcomes", "CO1: x",
             "BCA310-3: MOBILE APPLICATIONS", "Course Outcomes", "CO1: y"]
    sections = split_into_course_sections(lines)
    assert [(c, t) for c, t, _ in sections] == [("BCA108-3", "OPERATING SYSTEM"), ("BCA310-3", "MOBILE APPLICATIONS")]
    assert sections[0][2] == ["Course Outcomes", "CO1: x"]
