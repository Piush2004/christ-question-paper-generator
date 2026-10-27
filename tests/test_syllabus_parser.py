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
