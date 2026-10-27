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


def test_flatten_docx_drops_zero_width_space_only_lines_and_cleans_mixed_text(tmp_path):
    import docx
    doc = docx.Document()
    doc.add_paragraph("Real text")
    doc.add_paragraph("​")  # a line that is ONLY a zero-width space must not survive as "content"
    doc.add_paragraph("Mixed ​text")
    path = tmp_path / "zero_width.docx"
    doc.save(path)
    assert _flatten_docx(path) == ["Real text", "Mixed text"]


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
    ("BCA001- 1 C Programming", ("BCA001-1", "C Programming")),  # space between the code's dash and its suffix digit
    ("BCA221- 6 PRINCIPLES OF DATA SCIENCE", ("BCA221-6", "PRINCIPLES OF DATA SCIENCE")),
    ("BCA207A 3", None),  # a stray code+credit-count fragment is not a real heading (title has no real words)
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


CO_SECTION = [
    "Course Outcomes",
    "Upon completion of the course the student should be able to",
    "CO1: Demonstrate an understanding of the basic working process of an operating system.",
    "CO2: Explain the importance of process and scheduling.",
    "CO3: Analyse the issues in synchronization and memory management.",
]


def test_extract_course_outcomes_docx_style():
    from src.extraction.syllabus_parser import extract_course_outcomes
    assert extract_course_outcomes(CO_SECTION) == {
        "CO1": "Demonstrate an understanding of the basic working process of an operating system.",
        "CO2": "Explain the importance of process and scheduling.",
        "CO3": "Analyse the issues in synchronization and memory management.",
    }


def test_extract_course_outcomes_pdf_style_no_space_after_colon():
    from src.extraction.syllabus_parser import extract_course_outcomes
    lines = ["Course Outcome", "CO1: Infer on the step for problem solving using programming language",
             "CO2:Understand the fundamentals of C programming, including its history and features of C"]
    out = extract_course_outcomes(lines)
    assert out["CO1"] == "Infer on the step for problem solving using programming language"
    assert out["CO2"] == "Understand the fundamentals of C programming, including its history and features of C"


UNIT_SECTION = [
    "Unit 1 \t\t\t\t\t\t\t\t\t Teaching hours:09",
    "Introduction",
    "Categories of Operating Systems- Computer-System Organization- Computer-System Architecture",
    "System Structures",
    "Operating-System Services- User Operating-System Interface- System Calls",
    "Unit 2 \t\t\t\t\t\t\t\t\t Teaching hours:09",
    "Scheduling and Synchronization",
    "CPU Scheduling- Basic Concepts- Scheduling Criteria- Scheduling Algorithms",
    "Text Books and Reference Books:",
    "Silberschatz- P.B. Galvin and G. Gagne- Operating System Concepts.",
]


def test_extract_units():
    from src.extraction.syllabus_parser import extract_units
    units = extract_units(UNIT_SECTION)
    assert len(units) == 2
    assert units[0].number == 1 and units[0].teaching_hours == 9
    assert units[0].title == "Introduction"
    assert "Categories of Operating Systems" in units[0].topics and "System Structures" in units[0].topics
    assert units[1].number == 2 and units[1].teaching_hours == 9
    assert "Text Books" not in units[1].topics   # stop marker must not leak into the unit's topics


ROMAN_UNIT_SECTION = [
    "Unit I \t\t\t\t\t\t\t\t\t Teaching hours:10",
    "Network Fundamentals",
    "Introduction to computer networks- OSI model- TCP/IP model",
    "Unit II \t\t\t\t\t\t\t\t\t Teaching hours:10",
    "Data Link Layer",
    "Framing- Error detection- MAC addressing",
]


def test_extract_units_supports_roman_numerals():
    from src.extraction.syllabus_parser import extract_units
    units = extract_units(ROMAN_UNIT_SECTION)
    assert len(units) == 2
    assert units[0].number == 1 and units[0].title == "Network Fundamentals"
    assert units[1].number == 2 and units[1].title == "Data Link Layer"


def test_extract_units_skips_non_letter_lines_when_searching_for_title():
    from src.extraction.syllabus_parser import extract_units
    lines = ["Unit 1 Teaching hours:09", "3", "Real Title Here", "some topic text",
             "Unit 2 Teaching hours:05", "Second Title", "more content"]
    units = extract_units(lines)
    assert units[0].title == "Real Title Here"
    assert units[1].title == "Second Title"


TEACHING_HOURS_ON_OWN_LINE_SECTION = [
    "Unit-1",
    "Teaching Hours: 15",
    "SOFTWARE ENGINEERING AND DBMS",
    "Software Engineering: Nature of software- Defining software, Software Application Domains",
    "Unit-2",
    "Teaching Hours: 15",
    "DATABASE DESIGN",
    "more content here",
]


def test_extract_units_finds_teaching_hours_on_its_own_line():
    # Confirmed real layout (2025-26 PDF): "Teaching Hours: N" is its own line, separate from "Unit-N" —
    # it must not be mistaken for the unit's title.
    from src.extraction.syllabus_parser import extract_units
    units = extract_units(TEACHING_HOURS_ON_OWN_LINE_SECTION)
    assert len(units) == 2
    assert units[0].number == 1 and units[0].teaching_hours == 15
    assert units[0].title == "SOFTWARE ENGINEERING AND DBMS"
    assert units[1].number == 2 and units[1].teaching_hours == 15
    assert units[1].title == "DATABASE DESIGN"


def test_units_are_valid_rejects_blank_titles_and_duplicate_numbers():
    from src.extraction.syllabus_parser import SyllabusUnit, _units_are_valid
    assert not _units_are_valid([SyllabusUnit(1, "​", "x", None), SyllabusUnit(2, "Real Title", "y", None)])
    assert not _units_are_valid([SyllabusUnit(1, "Unit One", "x", None), SyllabusUnit(1, "Unit Two", "y", None)])
    assert _units_are_valid([SyllabusUnit(1, "Real Title", "x", None)])
    assert _units_are_valid([])


def test_parse_syllabus_file_operating_system():
    from src.extraction.syllabus_parser import parse_syllabus_file
    courses = parse_syllabus_file(SYLLABUS_DIR / "BCA (2024-25) PS_Final_2nd year.docx")
    os_course = next(c for c in courses if "OPERATING SYSTEM" in c.title.upper())
    assert os_course.course_outcomes["CO1"].startswith("Demonstrate an understanding")
    assert len(os_course.units) >= 5
    assert os_course.units[0].number == 1


def test_build_syllabus_writes_json_and_reports_coverage(tmp_path, monkeypatch, capsys):
    import scripts.build_syllabus as bs
    monkeypatch.setattr(bs, "OUT_PATH", tmp_path / "syllabus.json")
    bs.main()
    import json
    data = json.loads((tmp_path / "syllabus.json").read_text(encoding="utf-8"))
    assert "operating_systems" in data and "discrete_mathematics" in data
    assert data["operating_systems"]["course_outcomes"]["CO1"].startswith("Demonstrate an understanding")
    out = capsys.readouterr().out
    assert "graph_theory" in out.lower()  # must be reported as a declared-but-unmatched course, per Review Focus
    # BCA106-2 (Java Programming) is parsed with real units but loses the cross-file dedup for its family —
    # the "declared but unparsed" report must compare against every parsed candidate, not just dedup winners,
    # or a genuinely-parsed course is falsely reported as missing.
    assert "BCA106-2" not in out


def test_pick_winner_prefers_candidate_with_units_over_one_without():
    from scripts.build_syllabus import _pick_winner
    from src.extraction.syllabus_parser import SyllabusCourse, SyllabusUnit
    no_units = SyllabusCourse("BCA203-1", "PSD", "BCA(2025-26) PS-Final_1st year.pdf", {"CO1": "a"}, [])
    with_units = SyllabusCourse("BCA205-1", "PSD", "BCA (2024-25) PS_Final_2nd year.docx", {"CO1": "a"},
                                [SyllabusUnit(1, "Intro", "x", None)])
    winner = _pick_winner([no_units, with_units], dataset_code="BCA103-1")
    assert winner is with_units


def test_families_with_zero_units_reports_matched_but_empty():
    from scripts.build_syllabus import _families_with_zero_units
    from src.extraction.syllabus_parser import SyllabusCourse, SyllabusUnit
    by_family = {
        "a": SyllabusCourse("C1", "A", "f", {}, [SyllabusUnit(1, "x", "y", None)]),
        "b": SyllabusCourse("C2", "B", "f", {"CO1": "z"}, []),
    }
    assert _families_with_zero_units(by_family) == ["b"]
