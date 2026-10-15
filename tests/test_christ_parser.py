"""The layout-aware parser is verified against the real papers supplied by the project owner:
every paper must reproduce its own printed structure (section item counts, marks that add up to the
printed totals and to Max Marks, CO + RBT on every question)."""
from pathlib import Path

import pytest

from src.extraction.christ_parser import parse_paper

ROOT = Path(__file__).resolve().parents[1]
PAPERS = sorted((ROOT / "Question Papers").glob("*.pdf"))
pytestmark = pytest.mark.skipif(len(PAPERS) == 0, reason="real papers not present")


@pytest.mark.parametrize("pdf", PAPERS, ids=lambda p: p.name)
def test_real_paper_is_fully_verified(pdf):
    p = parse_paper(pdf)
    hard = [w for w in p.warnings if "very short text" not in w]
    assert hard == []
    assert p.course_code and p.max_marks and p.sections
    assert sum(s.total_marks for s in p.sections) == p.max_marks
    assert all(q.course_outcomes and q.rbt and q.marks for q in p.questions)
    assert all(lv in {f"L{i}" for i in range(1, 7)} for q in p.questions for lv in q.rbt)


def test_known_values_os2024():
    p = parse_paper(ROOT / "Question Papers" / "os2024.pdf")
    assert (p.course_code, p.semester, p.max_marks, p.duration_minutes) == ("BCA202-3", 3, 100, 180)
    assert [(s.label, s.marks_per_question, s.questions_to_answer) for s in p.sections] == [("A", 2, 10), ("B", 5, 6), ("C", 10, 5)]
    q1 = p.questions[0]
    assert q1.text.startswith("What is a Kernel") and q1.marks == 2 and q1.course_outcomes == ["CO1"] and q1.rbt == ["L2"]
    alts = [q for q in p.questions if q.kind == "alt"]
    assert alts and all(q.part in ("a", "b") for q in alts)


def test_table_layout_known_values():
    p = parse_paper(ROOT / "Question Papers" / "BCA434.pdf")
    assert p.layout == "table" and len([q for q in p.questions if q.section == "A"]) == 10
    assert [s.total_marks for s in p.sections] == [20, 30, 50]
