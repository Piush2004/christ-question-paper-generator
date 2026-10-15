"""Adversarial extraction tests (Phase 0.5 hardening, master-prompt-phase-0.5 §3).

Goal: confirm the extraction engine never crashes on difficult real-world formatting, and document
(via assertions) exactly what it does with each case — including known, accepted limitations. Where a
case reveals a genuine bug, it is fixed in src/extraction/ rather than the test being weakened.
"""

from pathlib import Path

from src.extraction.engine import QuestionExtractor
from src.ingestion.loaders import DocumentText, Page, load_document

FIXTURES = Path(__file__).parent / "fixtures"
ADVERSARIAL = FIXTURES / "adversarial"


def _extract_text(text: str) -> list:
    doc = DocumentText(source_path=Path("in_memory.txt"), pages=[Page(page_number=1, text=text)])
    return QuestionExtractor().extract(doc)


# --- numbering schemes (§3 "Numbering") ---

def test_bare_q_numbering_no_period_no_inline_text():
    text = "Q1\nWhat is a neural network?\nQ2\nWhat is backpropagation?\nQ3\nWhat is a loss function?\n"
    questions = _extract_text(text)
    assert [q.question_number_raw for q in questions] == ["1", "2", "3"]
    assert "neural network" in questions[0].raw_text.lower()


def test_dot_numbering():
    text = "1.\nWhat is precision?\n2.\nWhat is recall?\n3.\nWhat is F1 score?\n"
    questions = _extract_text(text)
    assert [q.question_number_raw for q in questions] == ["1", "2", "3"]


def test_paren_numbering():
    text = "1) What is precision?\n2) What is recall?\n3) What is F1 score?\n"
    questions = _extract_text(text)
    assert [q.question_number_raw for q in questions] == ["1", "2", "3"]


# --- sections (§3 "Sections") ---

def test_section_and_part_headers_variants():
    text = (
        "SECTION A\n1. Define entropy.\n"
        "SECTION B\n2. Define perplexity.\n"
        "PART I\n3. Define cross-entropy.\n"
        "PART II\n4. Define KL divergence.\n"
    )
    questions = _extract_text(text)
    sections = [q.section_label for q in questions]
    assert sections == ["SECTION A", "SECTION B", "PART I", "PART II"]


# --- nested questions (§3 "Nested questions") ---

def test_deeply_nested_three_subquestions():
    text = (
        "Q1\n"
        "(a) Define bias.\n"
        "(b) Define variance.\n"
        "(c) Define irreducible error.\n"
        "Q2\n"
        "(i) State Bayes theorem.\n"
        "(ii) Derive the posterior for a Gaussian likelihood.\n"
    )
    questions = _extract_text(text)
    numbers = [q.question_number_raw for q in questions]
    assert numbers == ["1(a)", "1(b)", "1(c)", "2(i)", "2(ii)"]
    assert all(q.is_subquestion for q in questions)
    assert questions[0].parent_number_raw == "1"
    assert questions[3].parent_number_raw == "2"


# --- mixed numbering within one paper (§3 "Mixed numbering") ---

def test_mixed_numbering_scheme_in_one_document():
    text = (
        "1. Answer the following.\n"
        "2. Answer the following.\n"
        "(a) Define overfitting.\n"
        "(b) Define underfitting.\n"
        "3. Answer any one.\n"
        "(i) Explain gradient descent.\n"
        "(ii) Explain stochastic gradient descent.\n"
    )
    questions = _extract_text(text)
    numbers = [q.question_number_raw for q in questions]
    # Q1 has no subparts -> emitted standalone; Q2/Q3 have subparts -> only children emitted.
    assert numbers == ["1", "2(a)", "2(b)", "3(i)", "3(ii)"]


# --- marks variants, including marks on their own line (§3 "Marks" / "Multiple marks") ---

def test_marks_on_separate_line():
    text = "1. Explain the CAP theorem.\n[10 Marks]\n2. Define ACID properties.\n(5)\n"
    questions = _extract_text(text)
    assert questions[0].marks == 10.0
    assert questions[1].marks == 5.0


def test_marks_beside_subquestions():
    text = (
        "1\n"
        "(a) Define recall. [3]\n"
        "(b) Define precision. [3]\n"
    )
    questions = _extract_text(text)
    assert questions[0].marks == 3.0
    assert questions[1].marks == 3.0


def test_marks_all_documented_variants():
    text = (
        "1. Q with square brackets [5]\n"
        "2. Q with paren marks (5 Marks)\n"
        "3. Q with bracket marks and word [10 Marks]\n"
        "4. Q with trailing M 5M\n"
        "5. Q with spelled out marks 10 Marks\n"
    )
    questions = _extract_text(text)
    assert [q.marks for q in questions] == [5.0, 5.0, 10.0, 5.0, 10.0]


# --- formatting corruption (§3) — must not crash, and must not silently destroy raw content ---

def test_corruption_fixture_does_not_crash_and_preserves_raw_text():
    doc = load_document(ADVERSARIAL / "corruption_and_noise.txt")
    questions = QuestionExtractor().extract(doc)
    assert len(questions) == 2
    assert questions[0].marks == 10.0
    assert questions[1].marks == 10.0
    # KNOWN LIMITATION (documented in docs/PHASE_0_5_AUDIT.md): repeated institution
    # header/footer and page-number noise lines are NOT stripped from raw_text by design —
    # raw_text must remain a byte-for-byte-faithful slice of the source (§9). Stripping such
    # noise is normalization/cleaning, deferred to src/preprocessing/ which produces
    # `question_text` from `raw_text` without mutating the original.
    assert "CHRIST UNIVERSITY" in questions[0].raw_text
    # hyphenated word broken across a line-wrap is preserved verbatim, not silently rejoined here
    assert "trade-" in questions[1].raw_text


def test_excessive_whitespace_still_detected():
    text = "Q1.        Explain     overfitting.     [10]\n\n\n\n\nQ2. Define bias.   [5]\n"
    questions = _extract_text(text)
    assert len(questions) == 2
    assert questions[0].marks == 10.0


# --- tables (§3 "Tables") — documented limitation, not a crash ---

def test_table_like_layout_does_not_crash():
    doc = load_document(ADVERSARIAL / "table_like.txt")
    questions = QuestionExtractor().extract(doc)
    # The numbering column is still detected because it's a line-leading "1." / "2." / "3." token;
    # inline marks in a separate whitespace-padded column ARE matched by MARKS_PATTERN's bare
    # "\d+\s*M\b"-style variants only when marks are unambiguous — here the column layout means
    # the number appears without a marks unit suffix, so it is NOT picked up as marks (a bare "5"
    # with no unit is correctly NOT treated as marks, to avoid false positives on random numbers
    # in question text). This is a known limitation: table-formatted mark columns need a
    # dedicated table-aware extractor, out of scope for the rule-based line engine (see
    # docs/PHASE_0_5_AUDIT.md).
    assert len(questions) == 3
    assert questions[0].marks is None


# --- mathematical content, Greek letters, subscripts/superscripts (§3) ---

def test_math_and_greek_content_passes_through_unmodified():
    text = (
        "1. Derive the closed-form solution for ridge regression: "
        "θ = (XᵀX + λI)⁻¹Xᵀy, where λ ≥ 0 "
        "and explain the role of α₂ in the regularization term. [10]\n"
    )
    questions = _extract_text(text)
    assert len(questions) == 1
    assert "λ" in questions[0].raw_text
    assert questions[0].marks == 10.0


# --- code content (§3 "Code") ---

def test_code_question_body_preserved():
    text = (
        "1. Trace the output of the following code and explain your reasoning:\n"
        "def f(n):\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    return f(n - 1) + f(n - 2)\n"
        "print(f(6)) [8]\n"
    )
    questions = _extract_text(text)
    assert len(questions) == 1
    assert "def f(n):" in questions[0].raw_text
    assert questions[0].marks == 8.0


# --- long vs very short questions (§3) ---

def test_long_multi_paragraph_question():
    body = "\n".join([f"This is paragraph {i} of a long question about distributed systems." for i in range(1, 8)])
    text = f"1. {body} [20]\n2. Short one. [2]\n"
    questions = _extract_text(text)
    assert len(questions) == 2
    assert len(questions[0].raw_text) > len(questions[1].raw_text)
    assert questions[0].extraction_confidence == 1.0


def test_very_short_one_line_question_has_lower_confidence_when_no_marks():
    text = "1. Hi\n2. Explain the Turing test in detail with examples. [10]\n"
    questions = _extract_text(text)
    assert questions[0].extraction_confidence < questions[1].extraction_confidence


# --- empty / malformed (§3) ---

def test_empty_page_produces_no_questions():
    doc = DocumentText(source_path=Path("empty.txt"), pages=[Page(page_number=1, text="")])
    assert QuestionExtractor().extract(doc) == []


def test_no_pages_at_all_produces_no_questions():
    doc = DocumentText(source_path=Path("nopages.txt"), pages=[])
    assert QuestionExtractor().extract(doc) == []


def test_prose_with_no_question_markers_produces_no_questions():
    text = "This document is the syllabus overview and contains no numbered questions whatsoever."
    assert _extract_text(text) == []
