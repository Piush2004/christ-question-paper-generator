from pathlib import Path

from src.extraction.engine import QuestionExtractor
from src.ingestion.loaders import DocumentText, Page, load_document

FIXTURES = Path(__file__).parent / "fixtures"


def _extract_text(text: str) -> list:
    doc = DocumentText(source_path=Path("in_memory.txt"), pages=[Page(page_number=1, text=text)])
    return QuestionExtractor().extract(doc)


def test_source_provenance_traceable_to_exact_lines():
    doc = load_document(FIXTURES / "sample_sections.txt")
    questions = QuestionExtractor().extract(doc)

    q1a = questions[0]
    assert q1a.page_number == 1
    assert q1a.source_line_start >= 0
    assert q1a.source_line_end > q1a.source_line_start
    # the raw_text preserved must be reconstructable from the source file at these exact lines
    all_lines = doc.full_text.split("\n")
    reconstructed = "\n".join(all_lines[q1a.source_line_start:q1a.source_line_end]).strip()
    assert reconstructed == q1a.raw_text


def test_extracts_simple_q_style_with_bracket_marks():
    doc = load_document(FIXTURES / "sample_simple.txt")
    questions = QuestionExtractor().extract(doc)

    assert len(questions) == 3
    numbers = [q.question_number_raw for q in questions]
    assert numbers == ["1", "2", "3"]
    assert all(not q.is_subquestion for q in questions)
    assert questions[0].marks == 10.0
    assert questions[1].marks == 5.0
    assert questions[2].marks == 5.0
    assert "overfitting" in questions[0].raw_text.lower()


def test_extracts_sections_and_nested_subquestions():
    doc = load_document(FIXTURES / "sample_sections.txt")
    questions = QuestionExtractor().extract(doc)

    # Q1 has (a)/(b) subparts -> Q1 itself is not emitted standalone, only its children.
    # Q2 has (i)/(ii) subparts -> same.
    # Q3 has no subparts -> emitted standalone.
    numbers = [q.question_number_raw for q in questions]
    assert numbers == ["1(a)", "1(b)", "2(i)", "2(ii)", "3"]

    q1a = questions[0]
    assert q1a.is_subquestion is True
    assert q1a.parent_number_raw == "1"
    assert q1a.marks == 5.0
    assert q1a.section_label == "Section A"
    assert "bias-variance" in q1a.raw_text.lower()
    # stem text ("Answer the following questions.") should be preserved, not discarded
    assert "answer the following questions" in q1a.raw_text.lower()

    q2i = questions[2]
    assert q2i.parent_number_raw == "2"
    assert q2i.marks == 10.0
    assert "gradient descent" in q2i.raw_text.lower()

    q3 = questions[4]
    assert q3.is_subquestion is False
    assert q3.section_label == "Section B"
    assert q3.marks == 15.0
    assert "neural networks" in q3.raw_text.lower()


def test_extracts_nothing_from_body_text_with_no_markers():
    questions = _extract_text("This is just a paragraph with no question numbering at all.")
    assert questions == []


def test_marks_patterns_variants():
    questions = _extract_text(
        "1. Question with square brackets [12]\n"
        "2. Question with paren marks (8 Marks)\n"
        "3. Question with trailing M 6M\n"
    )
    assert [q.marks for q in questions] == [12.0, 8.0, 6.0]


def test_low_confidence_for_very_short_extraction():
    questions = _extract_text("1. Hi\n2. What is X? [5]\n")
    assert questions[0].extraction_confidence < questions[1].extraction_confidence
