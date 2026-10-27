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
