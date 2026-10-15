"""Every rendered paper must reproduce the CHRIST layout. We re-parse the rendered PDF with the very
parser that reads the real institutional papers and require it to recover the blueprint exactly."""
import pytest

from src.extraction.christ_parser import parse_paper
from src.generation.blueprint import Blueprint, SectionSpec
from src.generation.render import PaperQuestion, render_docx, render_pdf
from src.optimization.allocator import _choice_positions


def fake_paper(bp):
    qs, n = [], 0
    cos = sorted(bp.outcomes)
    for s in bp.sections:
        ch = _choice_positions(s.n_items, s.n_choice)
        for i in range(s.n_items):
            n += 1
            lvl, co = 1 + n % 6, cos[n % len(cos)]
            text = f"Explain synthetic test concept number {n} with a suitable example for the learners."
            qs.append(PaperQuestion(s.label, n, "a" if i in ch else None, text, s.marks_each, co, lvl))
            if i in ch:
                qs.append(PaperQuestion(s.label, n, "b", f"Describe alternative synthetic concept {n} in detail.", s.marks_each, co, lvl))
    return qs


BPS = {
    "100_marks_cs": dict(max_marks=100, duration_minutes=180, sections=[SectionSpec("A", 10, 2), SectionSpec("B", 6, 5, 2), SectionSpec("C", 5, 10, 2)]),
    "100_marks_maths": dict(max_marks=100, duration_minutes=180, sections=[SectionSpec("A", 8, 3, 3), SectionSpec("B", 7, 8, 3), SectionSpec("C", 2, 10, 1)]),
    "50_marks": dict(max_marks=50, duration_minutes=120, sections=[SectionSpec("A", 5, 2), SectionSpec("B", 4, 5, 1), SectionSpec("C", 2, 10, 1)]),
}


def make_bp(name):
    return Blueprint(course_code="BCA999-1", course_name="SYNTHETIC COURSE", semester=3, exam_session="November 2025",
                     outcomes={"CO1": "Understand alpha.", "CO2": "Apply beta.", "CO3": "Analyse gamma."},
                     syllabus_year="2025-2026", **BPS[name])


@pytest.mark.parametrize("name", BPS)
def test_rendered_pdf_roundtrips_through_the_institutional_parser(name, tmp_path):
    bp = make_bp(name)
    assert bp.validate() == []
    qs = fake_paper(bp)
    p = parse_paper(render_pdf(bp, qs, tmp_path / "p.pdf"))
    assert p.warnings == []
    assert (p.course_code, p.course_name, p.semester, p.max_marks, p.duration_minutes) == (
        "BCA999-1", "Synthetic Course", 3, bp.max_marks, bp.duration_minutes)
    assert p.exam_session == "November 2025" and p.program == "BCA"
    assert [(s.label, s.marks_per_question, s.questions_to_answer) for s in p.sections] == [
        (s.label, s.marks_each, s.n_items) for s in bp.sections]
    assert len(p.questions) == len(qs)
    assert sorted(p.outcomes) == ["CO1", "CO2", "CO3"]
    for got, want in zip(p.questions, qs):
        assert (got.number, got.marks, got.course_outcomes, got.rbt) == (want.item, want.marks, [want.co], [f"L{want.level}"])
        assert got.text.startswith(want.text[:30])


def test_docx_contains_same_structure(tmp_path):
    from docx import Document
    bp = make_bp("50_marks")
    d = Document(render_docx(bp, fake_paper(bp), tmp_path / "p.docx"))
    text = "\n".join(p.text for p in d.paragraphs) + "\n" + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    for needle in ["CHRIST (Deemed to be University), Bengaluru - 560029", "End Semester Examinations - November 2025",
                   "SEMESTER - III", "Course Code: BCA999-1", "Max Marks: 50", "Duration: 02:00", "Section A", "2*5=10",
                   "Section C", "10*2=20", "OR", "(CO1, L", "Revised Bloom's Taxonomy (RBT) Levels"]:
        assert needle in text, needle
