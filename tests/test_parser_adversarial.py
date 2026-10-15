"""Adversarial inputs: the parser must fail loudly or report warnings — never invent a paper."""
import pytest
from fpdf import FPDF

from src.extraction.christ_parser import PaperParseError, parse_paper


def _pdf(tmp_path, lines, name="x.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for ln in lines:
        pdf.cell(0, 6, ln, new_x="LMARGIN", new_y="NEXT")
    p = tmp_path / name
    pdf.output(str(p))
    return p


def test_corrupt_pdf_raises_typed_error(tmp_path):
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"%PDF-1.4 this is not really a pdf \x00\x01\x02")
    with pytest.raises(PaperParseError):
        parse_paper(f)


def test_empty_file_raises_typed_error(tmp_path):
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"")
    with pytest.raises(PaperParseError):
        parse_paper(f)


def test_non_paper_pdf_yields_warnings_not_questions(tmp_path):
    p = parse_paper(_pdf(tmp_path, ["Lorem ipsum dolor sit amet", "1) not a question paper", "2) just a list"]))
    assert p.questions == [] and any("no questions" in w for w in p.warnings)


def test_malformed_item_without_marks_terminator_is_reported_not_invented(tmp_path):
    lines = ["Course Code: BCA999", "Course Name: TEST", "Max Marks: 4", "Duration: 01:00", "Course Outcome: Students will be able to:",
             "CO1: Do things.", "1) A question whose marks line is missing entirely",
             "2) A second question that is well formed", "4        (CO1, L3)", "2*1=4", "Section A"]
    p = parse_paper(_pdf(tmp_path, lines))
    # every question that IS returned carries real labels; the broken item is flagged, never silently completed
    assert all(q.marks and q.course_outcomes and q.rbt for q in p.questions)
    assert any(w.startswith("Q1") or "Section A" in w or "non-contiguous" in w for w in p.warnings)
