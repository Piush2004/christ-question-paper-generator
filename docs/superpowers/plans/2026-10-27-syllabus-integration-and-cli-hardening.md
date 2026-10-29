# Syllabus Integration and CLI Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the 3 real CHRIST BCA syllabus documents found in `Question Papers/BCA/` into verified Course-Outcome + Unit/topic data, wire it into the generation pipeline so topic grounding stops being purely unsupervised clustering wherever a real syllabus match exists, and add a preflight check that makes the existing CLI (`scripts/generate_paper.py`) fail fast and clearly when its environment (Ollama, model, packages) isn't ready.

**Architecture:** A new text-pattern parser (`src/extraction/syllabus_parser.py`) turns the two `.docx` and one `.pdf` syllabus files into `SyllabusCourse` records (code, title, course outcomes, units). `scripts/build_syllabus.py` runs it over all 3 files, joins each result to the existing `course_family` key, and writes `data/processed/syllabus.json`. `src/generation/topics.py`'s `build_history()` gets an optional `syllabus` parameter: when given a course with ≥1 unit, clusters are built directly from syllabus units (one per unit) instead of KMeans; when absent, the existing unsupervised path is unchanged — this is additive, not a rewrite. `src/generation/pipeline.py` loads `syllabus.json` automatically and reports the new provenance honestly. A separate, independent `scripts/check_environment.py` validates the runtime environment before generation.

**Tech Stack:** No new dependencies. Reuses `python-docx` and `pymupdf` (already used by `src/extraction/christ_parser.py`), the existing `src/embeddings/encoder.py`, and the existing `OllamaClient`.

**Spec:** No separate spec document exists; this plan implements the gap named in `docs/VALIDITY_AUDIT.md` (§Q2 "Are Bloom targets source-grounded?", §Q3 "Where did the topic labels come from?", §D "What may and may not be claimed" — topics are currently unsupervised clusters, explicitly *not* verified syllabus units) and `docs/GENERATION_ENGINE.md` ("Hard constraints, soft targets, and preferences" section, which currently hard-codes topic as PREFERENCE/unverified). Scope (syllabus integration + CLI hardening, not a new ML model or a web app) was confirmed directly with the project owner in this conversation.

## Global Constraints

- No new third-party dependencies — `python-docx`, `pymupdf`, `sentence-transformers` (via `src/embeddings/encoder.py`), `ortools`, and the existing `OllamaClient` cover everything this plan needs.
- Never fabricate syllabus content: a course with no detected Course-Outcomes or Unit section must be **absent** from `syllabus.json` and named in the coverage report — never backfilled with empty/placeholder units.
- The existing unsupervised-cluster path in `build_history()` must remain byte-for-byte unchanged in behavior when no syllabus match exists for a course (regression safety for all 131 existing tests).
- `HistoryProfile`'s new field must be added **last**, with a default, so the existing positional construction in `tests/test_allocator.py::make_profile()` (8 positional args) keeps working unchanged.
- `scripts/` already has `__init__.py`; new scripts may be imported by tests the same way `scripts/eval_bloom_leave_paper_out.py` already imports from `scripts/train_bloom.py`.

## Review Focus

- **Course-name/numbering mismatches silently drop a real syllabus match.** Confirmed real case: syllabus titles use Arabic numerals ("PRINCIPLES OF SOFTWARE DEVELOPMENT – 2"), our dataset's `course_family()` only recognizes Roman numerals ("- II") for the PSD split, so a real match would silently fall through to the wrong family. Owned by Task 2 (heading extraction + code normalization) and Task 4 (`course_family()` fix, with a test pinning both the Arabic and Roman forms).
- **A course listed in the semester table but with no detected Course-Outcomes/Unit section must be reported, never silently dropped or fabricated.** Confirmed real case: `BCA404-4 GRAPH THEORY` appears in the semester-IV course table of the 2024-25 syllabus file, but no CO/Unit section for it was found between the Python and Dot Net sections. Owned by Task 4's coverage report.
- **The same course appears in multiple syllabus files (different academic years) with possibly different CO wording.** Owned by Task 4's explicit "most recent source file wins" dedup rule.
- **Wiring syllabus-based clustering into `build_history()` must not change behavior for the courses that have no syllabus match, and must not break the existing leakage/allocation guarantees** (`tests/test_no_leakage.py`, `tests/test_allocator.py`, `tests/test_generator_fake_llm.py`). Owned by Task 5 (explicit `syllabus=None` regression test) and Task 7's final full-suite run.
- **The environment preflight check must not give a false PASS when Ollama is reachable but the configured model isn't pulled.** Owned by Task 8, which reuses `OllamaClient.is_available()`'s existing exact-model-name check rather than writing a new, looser one.

---

## File Structure

- Create: `src/extraction/syllabus_parser.py` — `SyllabusUnit`, `SyllabusCourse` dataclasses + the parsing pipeline (Tasks 1–4)
- Create: `scripts/build_syllabus.py` — CLI entry point producing `data/processed/syllabus.json` (Task 4)
- Create: `tests/test_syllabus_parser.py` — tests for the above, against the real files in `Question Papers/BCA/` (Tasks 1–4)
- Modify: `scripts/build_dataset.py` — fix `course_family()`'s PSD Arabic/Roman numeral gap (Task 4)
- Modify: `src/generation/topics.py` — `HistoryProfile.topics_source` field, `build_history(..., syllabus=...)` (Task 5)
- Create: `tests/test_topics_syllabus.py` — syllabus-driven clustering + `syllabus=None` regression test (Task 5)
- Modify: `src/generation/pipeline.py` — `constraint_provenance()` reports syllabus provenance; `history_for()` auto-loads `syllabus.json` (Tasks 6–7)
- Modify: `tests/test_validate.py` — one new test for `constraint_provenance()` (Task 6)
- Modify: `docs/GENERATION_ENGINE.md` — note the syllabus-grounded case (Task 6)
- Create: `tests/test_pipeline_syllabus.py` — `history_for()` with/without `syllabus.json` present (Task 7)
- Create: `scripts/check_environment.py` — preflight check (Task 8)
- Create: `tests/test_check_environment.py` — tests for the above (Task 8)
- Modify: `README.md` — setup/troubleshooting note (Task 8)

---

### Task 1: Flatten the syllabus documents into line streams

**Files:**
- Create: `src/extraction/syllabus_parser.py`
- Test: `tests/test_syllabus_parser.py`

**Interfaces:**
- Produces: `_flatten_docx(path: Path) -> list[str]`, `_flatten_pdf(path: Path) -> list[str]` — both return non-empty paragraph/line text in document order, used by Task 2 onward.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_syllabus_parser.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (module doesn't exist yet).

- [ ] **Step 3: Implement `_flatten_docx` and `_flatten_pdf` in `src/extraction/syllabus_parser.py`**

`_flatten_docx`: open with `docx.Document(path)`, return `[p.text.strip() for p in doc.paragraphs if p.text.strip()]` (do not touch `doc.tables` here — that's Task 4's job).
`_flatten_pdf`: open with `pymupdf.open(path, filetype="pdf")` (same call pattern as `src/extraction/christ_parser.py::parse_paper`), concatenate `page.get_text()` for all pages with `"\n"`, split on `"\n"`, return non-empty stripped lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/syllabus_parser.py tests/test_syllabus_parser.py
git commit -m "feat: flatten BCA syllabus docx/pdf files into line streams" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Course-heading detection and section splitting

**Files:**
- Modify: `src/extraction/syllabus_parser.py`
- Test: `tests/test_syllabus_parser.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (operates on `list[str]`, same shape `_flatten_docx`/`_flatten_pdf` produce).
- Produces: `_is_course_heading(line: str) -> tuple[str, str] | None` and `split_into_course_sections(lines: list[str]) -> list[tuple[str, str, list[str]]]` (each tuple is `(code, title, section_lines)`), used by Task 3 onward.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v -k "heading or split"`
Expected: FAIL (`ImportError`, names don't exist yet).

- [ ] **Step 3: Implement `_is_course_heading` and `split_into_course_sections`**

`_is_course_heading`: write a regex that extracts a course code (`B?CA` optionally followed by a space, 2–3 digits, an optional trailing letter/dash/digit suffix like `-1`, `E-A`, `319E`) from the start of the line, plus the remaining text as the title, trimmed of leading `-`, `–`, `:` separators and extra whitespace. If the code doesn't start with `B`, prefix it with `B`. Reject lines that are clearly not headings even if they start with digits/letters that could confuse a loose regex (use the two `None` fixtures above to drive this — e.g. require the code pattern to appear in the first ~15 characters and the remaining title text to be non-empty and not itself match a `CO\d` or known non-heading prefix).
`split_into_course_sections`: single pass over `lines`; whenever `_is_course_heading` matches, close the previous section (if any) and start a new one; all lines between headings (not including the heading line itself) become `section_lines` for the section that just closed... concretely: append non-matching lines to the *current* section's line list, same marker/span idea already used in `src/extraction/christ_parser.py` (`_Marker`/`_assign_spans`) — follow that pattern for consistency with this codebase.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v -k "heading or split"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/syllabus_parser.py tests/test_syllabus_parser.py
git commit -m "feat: detect course headings and split syllabus text into per-course sections" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Extract Course Outcomes and Units from a course section

**Files:**
- Modify: `src/extraction/syllabus_parser.py`
- Test: `tests/test_syllabus_parser.py`

**Interfaces:**
- Consumes: `section_lines: list[str]` shape produced by Task 2's `split_into_course_sections`.
- Produces: `SyllabusUnit` dataclass (`number: int`, `title: str`, `topics: str`, `teaching_hours: int | None`), `extract_course_outcomes(section_lines: list[str]) -> dict[str, str]`, `extract_units(section_lines: list[str]) -> list[SyllabusUnit]` — both used by Task 4.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v -k "extract"`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement `SyllabusUnit`, `extract_course_outcomes`, `extract_units`**

`SyllabusUnit`: `@dataclass` with fields `number: int`, `title: str`, `topics: str`, `teaching_hours: int | None`.
`extract_course_outcomes`: scan every line for a match against a pattern equivalent to `^CO\s*(\d+)\s*:\s*(.+)$` (case-insensitive on "CO"); build the dict from matches, no other state needed.
`extract_units`: scan for lines matching a pattern equivalent to `^unit[\s-]*(\d+)\b` (case-insensitive), optionally capturing `teaching\s*hours?\s*:?\s*(\d+)` from the same line; for each match, `title` = the next non-empty line, `topics` = every subsequent line joined with `". "` until the next unit-heading match or a line starting (case-insensitive) with one of: `"Text Books"`, `"Essential Reading"`, `"Reference"`, `"Web Resources"`, `"LAB EXERCISES"`, `"Course Objectives"`, `"CO – PO Mapping"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v -k "extract"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/syllabus_parser.py tests/test_syllabus_parser.py
git commit -m "feat: extract course outcomes and units from a syllabus course section" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Full parser, family join, and `syllabus.json` writer

**Files:**
- Modify: `src/extraction/syllabus_parser.py`
- Modify: `scripts/build_dataset.py` (fix `course_family()`)
- Create: `scripts/build_syllabus.py`
- Test: `tests/test_syllabus_parser.py`

**Interfaces:**
- Consumes: `scripts.build_dataset.course_family(name: str | None) -> str` (existing function, fixed in this task).
- Produces: `SyllabusCourse` dataclass (`code: str`, `title: str`, `source_file: str`, `course_outcomes: dict[str, str]`, `units: list[SyllabusUnit]`); `parse_syllabus_file(path: Path) -> list[SyllabusCourse]`; `data/processed/syllabus.json` with shape `{family: {code, title, source_file, course_outcomes, units: [{number, title, topics, teaching_hours}, ...]}}` — consumed by Task 7.

- [ ] **Step 1: Write the failing test for the `course_family()` fix**

```python
# add to tests/test_no_leakage.py (course_family is defined in scripts/build_dataset.py)
def test_course_family_handles_arabic_and_roman_psd_numerals():
    from scripts.build_dataset import course_family
    assert course_family("Principles Of Software Development – 2") == "psd_2"
    assert course_family("Principles Of Software Development - II") == "psd_2"
    assert course_family("Principles Of Software Development – 1") == "psd_1"
    assert course_family("Principles Of Software Development - I") == "psd_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_no_leakage.py -v -k psd_numerals`
Expected: FAIL (Arabic-numeral case returns `"psd_1"` instead of `"psd_2"`)

- [ ] **Step 3: Fix `course_family()` in `scripts/build_dataset.py`**

Change the `psd_2 if ... endswith(("- ii", "-ii", " ii")) else psd_1` check to also treat a trailing `2` (with the same dash/space separators) as `psd_2`, and a trailing `1` (or no numeral at all, as today) as `psd_1` — e.g. check `endswith(("- ii", "-ii", " ii", "- 2", "-2", " 2"))` for `psd_2`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_no_leakage.py -v -k psd_numerals`
Expected: PASS

- [ ] **Step 5: Write the failing test for `parse_syllabus_file` and the full build script**

```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py -v -k "parse_syllabus_file or build_syllabus"`
Expected: FAIL (`ImportError` / module doesn't exist)

- [ ] **Step 7: Implement `SyllabusCourse`, `parse_syllabus_file`, and `scripts/build_syllabus.py`**

`SyllabusCourse`: `@dataclass` with fields `code: str`, `title: str`, `source_file: str`, `course_outcomes: dict[str, str]`, `units: list[SyllabusUnit]`.
`parse_syllabus_file(path)`: dispatch to `_flatten_docx`/`_flatten_pdf` by suffix, run `split_into_course_sections`, for each `(code, title, section_lines)` build `course_outcomes = extract_course_outcomes(section_lines)` and `units = extract_units(section_lines)`; **skip** (do not emit) a section where both are empty — that's a false-positive heading match, not a real course, per the "never fabricate" constraint.
`scripts/build_syllabus.py`: module-level `OUT_PATH = ROOT / "data" / "processed" / "syllabus.json"` (so the test above can monkeypatch it); `main()` calls `parse_syllabus_file` on all 3 files under `Question Papers/BCA/*`, computes `course_family(c.title)` per course (import from `scripts.build_dataset`), and when two files produce the same family keeps the one from the alphabetically-latest filename among the matches whose name contains the later academic year (the three filenames already encode the year — `2023-24`, `2024-25`, `2025-26` — sort on that substring); writes the dict to `OUT_PATH`; then prints a coverage report comparing the resulting family set against the family set found in `data/processed/questions.jsonl` (read if present, skip the comparison otherwise) — explicitly naming any family present in the exam-paper dataset but absent from the syllabus (expected: likely `graph_theory`, confirm by running it) and, separately, any **declared** course code from the docx `doc.tables[0]` catalog (semester table) that has no matching parsed section (read `doc.tables[0]` directly in this script, not in the shared parser, since only the two `.docx` files have this table).

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_syllabus_parser.py tests/test_no_leakage.py -v`
Expected: PASS. Then run `.venv\Scripts\python.exe scripts/build_syllabus.py` once for real and read its printed coverage report — record which families matched and which didn't in the commit message or a short note, since this is real, previously-unknown information (e.g. confirm whether graph theory truly has no syllabus section anywhere, including the PDF).

- [ ] **Step 9: Commit**

```bash
git add src/extraction/syllabus_parser.py scripts/build_dataset.py scripts/build_syllabus.py tests/test_syllabus_parser.py tests/test_no_leakage.py data/processed/syllabus.json
git commit -m "feat: parse BCA syllabus files into syllabus.json with coverage report" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Syllabus-grounded topic clusters in `build_history()`

**Files:**
- Modify: `src/generation/topics.py`
- Create: `tests/test_topics_syllabus.py`

**Interfaces:**
- Consumes: `SyllabusCourse`/`SyllabusUnit` from `src/extraction/syllabus_parser.py` (Task 4); existing `encode()` from `src/embeddings/encoder.py`; existing `TopicCluster` dataclass (fields: `id: int`, `label: str`, `keywords: list[str]`, `member_ids: list[str]`, `centroid: np.ndarray`, `freq: int`, `co_counts: dict[str, int]`, `last_paper_id: str | None`) and `HistoryProfile` dataclass already in this file.
- Produces: `HistoryProfile.topics_source: str` (new field, default `"unsupervised_cluster"`, added **after** `excluded_from_exemplars` so existing positional construction in `tests/test_allocator.py` is unaffected); `build_history(..., syllabus: "SyllabusCourse | None" = None)` — consumed by Task 7.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_topics_syllabus.py
import numpy as np
from src.extraction.syllabus_parser import SyllabusCourse, SyllabusUnit
from src.generation.topics import build_history

def fake_questions():
    pairs = [
        ("q1", "Explain process scheduling and context switching in an operating system."),
        ("q2", "Describe CPU scheduling algorithms such as round robin and priority scheduling."),
        ("q3", "Explain file allocation methods and directory structures in a file system."),
        ("q4", "Describe disk scheduling algorithms and secondary storage structure."),
    ]
    return [{"question_id": qid, "paper_id": "P1", "text": t, "n_words": len(t.split()), "marks": 5.0,
             "course_outcomes": ["CO1"], "rbt": ["L2"]} for qid, t in pairs]

def fake_syllabus():
    return SyllabusCourse(code="BCA108-3", title="OPERATING SYSTEM", source_file="x.docx",
                          course_outcomes={"CO1": "a"},
                          units=[SyllabusUnit(1, "Process Management", "process scheduling context switching", 9),
                                 SyllabusUnit(2, "File Systems", "file allocation directory structure disk scheduling", 9)])

def test_build_history_uses_syllabus_units_when_given():
    qs = fake_questions()
    profile = build_history(qs, "operating_systems", ["P1"], qs, syllabus=fake_syllabus())
    assert profile.topics_source == "syllabus"
    assert len(profile.clusters) == 2
    assert {c.label for c in profile.clusters} == {"Process Management", "File Systems"}

def test_build_history_falls_back_to_unsupervised_when_no_syllabus():
    qs = fake_questions()
    profile = build_history(qs, "operating_systems", ["P1"], qs, syllabus=None)
    assert profile.topics_source == "unsupervised_cluster"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_topics_syllabus.py -v`
Expected: FAIL (`TypeError: build_history() got an unexpected keyword argument 'syllabus'`)

- [ ] **Step 3: Implement the `syllabus` parameter and `topics_source` field**

Add `topics_source: str = "unsupervised_cluster"` as the last field of `HistoryProfile`. Add `syllabus: "SyllabusCourse | None" = None` as the last parameter of `build_history()`. When `syllabus is not None and syllabus.units`: for each unit, embed `unit.title + ". " + unit.topics` via `encode()` to get its centroid directly (skip KMeans entirely); assign every eligible question (the same `qs`/`emb` already computed earlier in the function) to the unit whose centroid has highest cosine similarity (`np.argmax` over `emb[i] @ centroids.T`); build one `TopicCluster` per unit (`id` = unit index, `label` = `unit.title`, `keywords` = `unit.topics.split()[:6]`, `member_ids`/`co_counts`/`last_paper_id` populated the same way the existing KMeans branch already does, just driven by this assignment instead of `km.labels_`); set `topics_source = "syllabus"`. Otherwise keep the existing KMeans path unchanged and set `topics_source = "unsupervised_cluster"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_topics_syllabus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/generation/topics.py tests/test_topics_syllabus.py
git commit -m "feat: ground topic clusters in verified syllabus units when available" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Honest provenance for syllabus-grounded topics

**Files:**
- Modify: `src/generation/pipeline.py` (`constraint_provenance()`)
- Modify: `tests/test_validate.py`
- Modify: `docs/GENERATION_ENGINE.md`

**Interfaces:**
- Consumes: `profile.topics_source` from Task 5.
- Produces: updated `constraint_provenance(bp, profile, it) -> dict` `"topic"` value — consumed by `src/generation/pipeline.py::export()` (unchanged caller).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_validate.py
def test_constraint_provenance_reports_syllabus_grounded_topic_when_available():
    from types import SimpleNamespace as NS
    from src.generation.pipeline import constraint_provenance
    prof = NS(clusters=[NS(label="Process Management")], topics_source="syllabus")
    it = NS(cluster=0)
    bp = Blueprint(course_code="T", course_name="T", semester=1, exam_session="x", max_marks=4, duration_minutes=60,
                   outcomes={"CO1": "a"}, sections=[SectionSpec("A", 2, 2)])
    p = constraint_provenance(bp, prof, it)
    assert p["topic"].startswith("SOFT") and "verified syllabus unit" in p["topic"] and "Process Management" in p["topic"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_validate.py -v -k syllabus_grounded`
Expected: FAIL (`AttributeError` on `profile.topics_source`, or the string still says "PREFERENCE ... NOT a verified syllabus topic")

- [ ] **Step 3: Implement the provenance branch in `constraint_provenance()`**

In `src/generation/pipeline.py::constraint_provenance()`, change the `"topic"` line to branch on `getattr(profile, "topics_source", "unsupervised_cluster")`: when `"syllabus"`, return `f"SOFT — verified syllabus unit '{profile.clusters[it.cluster].label}' (CHRIST BCA syllabus)"`; otherwise keep the existing `"PREFERENCE — unsupervised cluster ... NOT a verified syllabus topic"` string unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_validate.py -v`
Expected: PASS (both the new test and the existing `test_constraint_provenance_separates_hard_soft_and_preference`, which must still pass unchanged since it doesn't set `topics_source`).

- [ ] **Step 5: Update `docs/GENERATION_ENGINE.md`**

In the "Hard constraints, soft targets, and preferences" table/section, add one sentence noting that when a course has a verified syllabus match (`data/processed/syllabus.json`), its topic provenance is reported as a SOFT target tied to a named syllabus unit instead of an unsupervised-cluster PREFERENCE, and that this is per-course (some courses, e.g. graph theory per the Task 4 coverage report, may have no syllabus match and keep the unsupervised path).

- [ ] **Step 6: Commit**

```bash
git add src/generation/pipeline.py tests/test_validate.py docs/GENERATION_ENGINE.md
git commit -m "feat: report syllabus-grounded topic provenance honestly" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Auto-load `syllabus.json` in `history_for()`, full regression run

**Files:**
- Modify: `src/generation/pipeline.py` (`history_for()`)
- Create: `tests/test_pipeline_syllabus.py`

**Interfaces:**
- Consumes: `data/processed/syllabus.json` (Task 4 output, may be absent).
- Produces: `history_for(family, papers, questions, exclude_paper_ids=None, seed=7, syllabus_path: Path | None = None) -> HistoryProfile` — `syllabus_path` is a new optional parameter (default: the real `ROOT / "data" / "processed" / "syllabus.json"`) so tests can point it at a fixture file instead of the real one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_syllabus.py
import json
from src.generation.pipeline import history_for
from src.generation.blueprint import load_papers, load_questions

def test_history_for_without_syllabus_file_does_not_crash(tmp_path):
    papers, questions = load_papers(), load_questions()
    profile = history_for("operating_systems", papers, questions, syllabus_path=tmp_path / "missing.json")
    assert profile.topics_source == "unsupervised_cluster"

def test_history_for_loads_matching_syllabus_entry(tmp_path):
    syllabus_path = tmp_path / "syllabus.json"
    syllabus_path.write_text(json.dumps({"operating_systems": {
        "code": "BCA108-3", "title": "OPERATING SYSTEM", "source_file": "x.docx",
        "course_outcomes": {"CO1": "a"},
        "units": [{"number": 1, "title": "Process Management", "topics": "process scheduling", "teaching_hours": 9},
                   {"number": 2, "title": "File Systems", "topics": "file allocation directory", "teaching_hours": 9}],
    }}), encoding="utf-8")
    papers, questions = load_papers(), load_questions()
    profile = history_for("operating_systems", papers, questions, syllabus_path=syllabus_path)
    assert profile.topics_source == "syllabus"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pipeline_syllabus.py -v`
Expected: FAIL (`TypeError: history_for() got an unexpected keyword argument 'syllabus_path'`)

- [ ] **Step 3: Implement the `syllabus_path` parameter in `history_for()`**

Add `syllabus_path: Path | None = None` as the last parameter, defaulting at call time to `ROOT / "data" / "processed" / "syllabus.json"` (mirror the existing `load_source_status()` pattern already in this file for "load a JSON file if it exists, else return an empty/None default"). If the file exists, load it, look up `data.get(family)`; if found, reconstruct a `SyllabusCourse`/`SyllabusUnit` from the dict (import both from `src.extraction.syllabus_parser`) and pass it as `build_history(..., syllabus=that_course)`; otherwise pass `syllabus=None`. Never raise if the file is absent or the family isn't a key.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pipeline_syllabus.py -v`
Expected: PASS

- [ ] **Step 5: Run the full existing test suite for regression**

Run: `.venv\Scripts\python.exe -m pytest tests -q`
Expected: all tests pass (131 previously-passing tests + the new ones from Tasks 1–7), with particular attention to `tests/test_no_leakage.py`, `tests/test_allocator.py`, and `tests/test_generator_fake_llm.py` (Review Focus item 4) — if any of these fail, the cause is almost certainly the new `HistoryProfile` field or `build_history`/`history_for` signature changes; fix forward, do not weaken the failing test.

- [ ] **Step 6: Commit**

```bash
git add src/generation/pipeline.py tests/test_pipeline_syllabus.py
git commit -m "feat: auto-load syllabus.json in history_for()" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Environment preflight check for the CLI

**Files:**
- Create: `scripts/check_environment.py`
- Create: `tests/test_check_environment.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing `src.llm.ollama.OllamaClient` (specifically its existing `is_available()` method — must be reused, not reimplemented, per Review Focus item 5).
- Produces: `EnvironmentReport` dataclass (`missing_packages: list[str]`, `ollama_reachable: bool`, `model_available: bool`, `ok: bool`, `messages: list[str]`), `check_environment(client=None, required_packages=DEFAULT_PACKAGES) -> EnvironmentReport`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_check_environment.py
from scripts.check_environment import check_environment, DEFAULT_PACKAGES

class _StubClient:
    def __init__(self, available): self._available = available; self.model = "qwen2.5:7b-instruct-q4_K_M"
    def is_available(self): return self._available

def test_all_pass():
    r = check_environment(client=_StubClient(True), required_packages=["json", "re"])  # stdlib, always importable
    assert r.ok is True and r.missing_packages == [] and r.ollama_reachable and r.model_available

def test_ollama_unreachable_fails_with_remediation_message():
    r = check_environment(client=_StubClient(False), required_packages=["json"])
    assert r.ok is False
    assert any("ollama pull qwen2.5:7b-instruct-q4_K_M" in m for m in r.messages)

def test_missing_package_fails_with_name():
    r = check_environment(client=_StubClient(True), required_packages=["json", "this_package_does_not_exist_xyz"])
    assert r.ok is False and "this_package_does_not_exist_xyz" in r.missing_packages
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_check_environment.py -v`
Expected: FAIL (`ImportError`, module doesn't exist)

- [ ] **Step 3: Implement `check_environment()` in `scripts/check_environment.py`**

`DEFAULT_PACKAGES = ["httpx", "pydantic", "numpy", "sentence_transformers", "ortools", "fpdf", "docx", "pymupdf"]`. `EnvironmentReport`: `@dataclass`. `check_environment(client=None, required_packages=DEFAULT_PACKAGES)`: if `client` is `None`, construct a real `OllamaClient()`; for each name in `required_packages` try `importlib.import_module(name)`, collect failures into `missing_packages`; `ollama_reachable` = whatever a bare `httpx.get` to the client's base URL indicates, OR simply reuse `client.is_available()` for both reachability and model-match in one call (since the existing method already does both — if it returns `False` you can't distinguish "server down" from "model missing" without a second check; add a small separate reachability probe only if you need the distinction for the message, otherwise report both under one message when `is_available()` is `False`); `model_available = client.is_available()`; `ok = not missing_packages and model_available`; build `messages` listing each failure with a concrete fix (`f"ollama pull {client.model}"` for the model case, `f"pip install {name}"` for each missing package). Add `if __name__ == "__main__":` that calls `check_environment()`, prints the report, and calls `sys.exit(0 if r.ok else 1)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_check_environment.py -v`
Expected: PASS

- [ ] **Step 5: Update `README.md`**

In the "Generate a paper" section, add one line before the example commands: run `.venv\Scripts\python.exe scripts/check_environment.py` first and confirm it prints `OK`. Add a short "Troubleshooting" subsection: Ollama not running → start the Ollama app/service; model missing → run the exact `ollama pull <model>` command the script prints; package import errors → re-run `pip install -r requirements.txt`.

- [ ] **Step 6: Run the full suite one final time**

Run: `.venv\Scripts\python.exe -m pytest tests -q`
Expected: all tests pass (the complete set from this plan plus the pre-existing 131).

- [ ] **Step 7: Commit**

```bash
git add scripts/check_environment.py tests/test_check_environment.py README.md
git commit -m "feat: add environment preflight check for the generation CLI" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** both confirmed scope items are covered — syllabus integration (Tasks 1–7: parse → join/family-fix → cluster-grounding → honest provenance → auto-load) and CLI hardening (Task 8: preflight + docs). No deployment beyond the CLI was requested or built, matching the "Harden the CLI" choice.
- **Step scan:** every implementation step carries an exact signature and either a pinned regex/constant list or says the test fully determines behavior; no step says "handle edge cases" or leaves a type undefined.
- **Type consistency:** `SyllabusUnit`/`SyllabusCourse` field names (`number`, `title`, `topics`, `teaching_hours`, `code`, `course_outcomes`, `units`) are used identically across Tasks 3, 4, 5, 7. `topics_source` and `syllabus`/`syllabus_path` parameter names are used identically across Tasks 5, 6, 7.
- **Review Focus:** all 5 items are each pinned to an owning task's test (numbering mismatch → Task 4 Step 1; missing section not fabricated → Task 4 Step 7's skip rule + Step 8's manual check; multi-file dedup → Task 4 Step 7's "latest year wins" rule; regression safety → Task 5 Step 1's `syllabus=None` test + Task 7 Step 5's full-suite run; false-PASS preflight → Task 8 reusing `is_available()`).
- **Proportion:** 8 tasks, ~40 steps, matching a genuinely new parser + one integration point + one new script — not a rewrite of anything existing.

---

Plan complete and saved to `docs/superpowers/plans/2026-10-27-syllabus-integration-and-cli-hardening.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** — a fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** — I implement every task myself in this session, then one fresh reviewer checks the whole branch at the end. Cheapest and fastest; no independent review until the end.

For this plan I recommend **Native**, because the 8 tasks are mostly linear (each builds directly on the previous one's exact interface, there's little independent/parallel work), the total scope is moderate (~13 files), and a shipped mistake here is cheap to catch — every task ends in a test run and Task 7/8 end in full-suite regression runs, so problems surface immediately rather than silently compounding. Does the plan capture what you want, and which approach should we use?
