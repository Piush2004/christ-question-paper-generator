"""Parse the real CHRIST BCA syllabus documents into data/processed/syllabus.json.

Joins each parsed course to the existing `course_family` key (scripts/build_dataset.py) so the
generation pipeline (src/generation/topics.py, src/generation/pipeline.py) can ground topic
clustering in verified syllabus units wherever a match exists. Never fabricates: a course with
no detected Course-Outcomes/Unit section is simply absent, and this script's coverage report
names it explicitly rather than silently dropping it.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import docx  # noqa: E402

from scripts.build_dataset import course_family  # noqa: E402
from src.extraction.syllabus_parser import SyllabusCourse, parse_syllabus_file  # noqa: E402

SYLLABUS_DIR = ROOT / "Question Papers" / "BCA"
OUT_PATH = ROOT / "data" / "processed" / "syllabus.json"
QUESTIONS_PATH = ROOT / "data" / "processed" / "questions.jsonl"
PAPERS_PATH = ROOT / "data" / "processed" / "papers.jsonl"

_YEAR = re.compile(r"20\d\d-\d\d")
_SEMESTER_SUFFIX = re.compile(r"-(\d+)$")
_CATALOG_CODE = re.compile(r"\bB?CA\s?\d{2,3}[A-Za-z]?(?:-[A-Za-z0-9]+)?\b", re.IGNORECASE)


def _year_of(filename: str) -> str:
    m = _YEAR.search(filename)
    return m.group(0) if m else ""


def _semester_suffix(code: str) -> str:
    m = _SEMESTER_SUFFIX.search(code)
    return m.group(1) if m else ""


def _dataset_course_codes() -> dict[str, str]:
    """family -> course_code actually seen in the real exam-paper dataset, if built."""
    if not PAPERS_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in PAPERS_PATH.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        out.setdefault(p["course_family"], p.get("course_code", ""))
    return out


def _pick_winner(candidates: list[SyllabusCourse], dataset_code: str) -> SyllabusCourse:
    """Prefer a candidate that actually has parsed units over one that doesn't — a syllabus "match" with
    no units is no better than no match for topic-grounding (src/generation/topics.py's build_history()
    only grounds on a syllabus when it has units), so picking one only hides the gap. Among candidates
    with units, prefer the one whose semester suffix matches the dataset's real exam-paper course code
    for this family — a syllabus revision that moved a course to a different semester (confirmed real
    case: Operating System is BCA108-3 in the 2024-25 syllabus but BCA105-2, a different semester, in
    the 2025-26 one) is a different course offering, not a newer edition of the same one, so "latest
    file wins" alone would ground topics in the wrong curriculum. Falls back to latest-file-wins when
    there's no dataset code to disambiguate, or none of the candidates match it."""
    with_units = [c for c in candidates if c.units]
    pool = with_units or candidates
    if dataset_code:
        suffix = _semester_suffix(dataset_code)
        matching = [c for c in pool if _semester_suffix(c.code) == suffix]
        if matching:
            pool = matching
    return max(pool, key=lambda c: _year_of(c.source_file))


def _families_with_zero_units(by_family: dict[str, SyllabusCourse]) -> list[str]:
    """Families that matched a syllabus course but ended up with no usable units — these silently fall
    back to unsupervised clustering in build_history() and must be named, not counted as fully matched."""
    return sorted(fam for fam, c in by_family.items() if not c.units)


def _declared_catalog_codes(path: Path) -> set[str]:
    """Course codes declared in the docx's semester course table (doc.tables[0])."""
    if path.suffix.lower() != ".docx":
        return set()
    doc = docx.Document(path)
    if not doc.tables:
        return set()
    codes = set()
    for row in doc.tables[0].rows:
        for cell in row.cells:
            for m in _CATALOG_CODE.finditer(cell.text):
                code = m.group(0).upper().replace(" ", "")
                if not code.startswith("B"):
                    code = "B" + code
                codes.add(code)
    return codes


def main() -> None:
    candidates: dict[str, list[SyllabusCourse]] = {}
    declared_codes: set[str] = set()
    all_parsed_codes: set[str] = set()
    for path in sorted(SYLLABUS_DIR.glob("*")):
        if path.suffix.lower() not in (".docx", ".pdf"):
            continue
        declared_codes |= _declared_catalog_codes(path)
        for course in parse_syllabus_file(path):
            fam = course_family(course.title)
            candidates.setdefault(fam, []).append(course)
            all_parsed_codes.add(course.code)

    dataset_codes = _dataset_course_codes()
    by_family = {fam: _pick_winner(cs, dataset_codes.get(fam, "")) for fam, cs in candidates.items()}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        fam: {
            "code": c.code,
            "title": c.title,
            "source_file": c.source_file,
            "course_outcomes": c.course_outcomes,
            "units": [dataclasses.asdict(u) for u in c.units],
        }
        for fam, c in by_family.items()
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(by_family)} courses to {OUT_PATH}")

    if QUESTIONS_PATH.exists():
        dataset_fams = {json.loads(l)["course_family"] for l in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()}
        missing = sorted(dataset_fams - set(by_family))
        if missing:
            print(f"Families in the exam-paper dataset with NO syllabus match: {missing}")
        else:
            print("Every exam-paper dataset family has a syllabus match.")
    else:
        print("data/processed/questions.jsonl not found — skipping dataset-coverage comparison.")

    unmatched_declared = sorted(declared_codes - all_parsed_codes)
    if unmatched_declared:
        print(f"Declared-but-unparsed course codes (semester catalog table): {unmatched_declared}")
    else:
        print("Every declared catalog course code has a matching parsed section.")

    zero_unit_fams = _families_with_zero_units(by_family)
    if zero_unit_fams:
        print(f"Families matched with zero parsed units (falls back to unsupervised clustering): {zero_unit_fams}")


if __name__ == "__main__":
    main()
