"""Build the structured question dataset from real CHRIST papers.

Sources (in priority order — earlier sources win when the same paper appears twice):
  1. ``Question Papers/``   — papers supplied by the project owner (11 PDFs)
  2. ``data/raw/databank``  — public university data-bank PDFs downloaded earlier in this project
  3. ``data/raw/knowledgepro/documents`` — same data bank, other file naming

A paper is *admitted* only if the layout-aware parser verifies it (no warnings other than short-text
notes; every question has marks + CO + RBT). Everything else is listed in the rejection report with
the reason — nothing is silently dropped. Exact-duplicate files and re-uploads of the same
(course code, exam session) are collapsed, so the same exam never lands in both train and test.

Outputs
  data/processed/questions.jsonl      one record per question/alternative/part
  data/processed/papers.jsonl         one record per admitted paper (header + section blueprint)
  data/processed/build_report.json    admitted / rejected papers and why
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extraction.christ_parser import ParsedPaper, parse_paper  # noqa: E402

OUT = ROOT / "data" / "processed"
SOURCES = [
    ("owner", sorted((ROOT / "Question Papers").glob("*.pdf"))),
    ("databank", sorted((ROOT / "data" / "raw" / "databank").glob("*.pdf"))),
    ("databank", sorted((ROOT / "data" / "raw" / "knowledgepro" / "documents").glob("*.dat"))),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def course_family(name: str | None) -> str:
    """Stable subject key shared across years/semesters (used for leakage-safe grouping)."""
    n = (name or "").lower()
    # A family is ONE course across years. Different courses of a series (Foundational vs Discrete
    # Mathematics, PSD-I vs PSD-II) have different outcomes/syllabi and must never share a family —
    # an earlier version merged them (found by the validity audit, docs/VALIDITY_AUDIT.md).
    if "principles of software" in n:
        return "psd_2" if n.rstrip().endswith(("- ii", "-ii", " ii")) else "psd_1"
    for key, fam in [("graph", "graph_theory"), ("discrete", "discrete_mathematics"),
                     ("foundational math", "foundational_mathematics"),
                     ("software engineering", "software_engineering"),
                     ("network", "computer_networks"), ("operating", "operating_systems"),
                     ("financial", "financial_accounting"), ("programming", "programming")]:
        if key in n:
            return fam
    return n.strip().replace(" ", "_") or "unknown"


def admit(p: ParsedPaper) -> tuple[bool, str]:
    if not p.questions:
        return False, "no questions parsed (unsupported legacy layout or scanned)"
    hard = [w for w in p.warnings if "very short text" not in w]
    if hard:
        return False, "verification failed: " + "; ".join(hard[:3])
    if any(not q.rbt or not q.course_outcomes or q.marks is None for q in p.questions):
        return False, "missing CO / RBT / marks labels"
    if not (p.course_code and p.exam_session):
        return False, "missing course code / exam session"
    return True, "ok"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen_hash: dict[str, str] = {}
    seen_exam: dict[tuple[str, str], str] = {}
    admitted: list[tuple[str, Path, ParsedPaper]] = []
    report: dict = {"admitted": [], "rejected": [], "duplicates": []}

    for origin, files in SOURCES:
        for f in files:
            h = sha256(f)
            if h in seen_hash:
                report["duplicates"].append({"file": str(f.relative_to(ROOT)), "same_as": seen_hash[h], "kind": "identical bytes"})
                continue
            seen_hash[h] = str(f.relative_to(ROOT))
            try:
                p = parse_paper(f)
            except Exception as exc:  # noqa: BLE001 - report, never crash the whole build
                report["rejected"].append({"file": str(f.relative_to(ROOT)), "reason": f"parser error: {exc}"})
                continue
            ok, why = admit(p)
            if not ok:
                report["rejected"].append({"file": str(f.relative_to(ROOT)), "reason": why})
                continue
            key = ((p.course_code or "").split("-")[0] + "|" + (p.course_name or ""), p.exam_session or "")
            if key in seen_exam:
                report["duplicates"].append({"file": str(f.relative_to(ROOT)), "same_as": seen_exam[key],
                                             "kind": "same course + exam session (re-upload)"})
                continue
            seen_exam[key] = str(f.relative_to(ROOT))
            admitted.append((origin, f, p))

    papers, questions = [], []
    for origin, f, p in admitted:
        pid = f"{(p.course_code or 'X').replace('/', '_')}_{(p.exam_session or '').replace(' ', '')}"
        papers.append({
            "paper_id": pid, "origin": origin, "file": str(f.relative_to(ROOT)),
            "course_code": p.course_code, "course_name": p.course_name, "course_family": course_family(p.course_name),
            "program": p.program, "semester": p.semester, "department": p.department,
            "exam_title": p.exam_title, "exam_session": p.exam_session, "academic_year": p.academic_year,
            "max_marks": p.max_marks, "duration_minutes": p.duration_minutes, "layout": p.layout,
            "outcomes": p.outcomes, "sections": [dataclasses.asdict(s) for s in p.sections],
        })
        for q in p.questions:
            qid = f"{pid}_Q{q.number}{q.part or ''}"
            questions.append({
                "question_id": qid, "paper_id": pid, "course_code": p.course_code,
                "course_family": course_family(p.course_name), "academic_year": p.academic_year,
                "exam_session": p.exam_session, "section": q.section, "number": q.number, "part": q.part,
                "kind": q.kind, "text": q.text, "marks": q.marks, "course_outcomes": q.course_outcomes,
                "rbt": q.rbt, "page": q.page, "label_source": "paper_setter",
                "n_words": len(q.text.split()),
            })
        report["admitted"].append({"paper_id": pid, "origin": origin, "file": str(f.relative_to(ROOT)),
                                   "questions": len(p.questions)})

    (OUT / "questions.jsonl").write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in questions), encoding="utf-8")
    (OUT / "papers.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in papers), encoding="utf-8")
    (OUT / "build_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"admitted papers: {len(papers)} | questions: {len(questions)} | rejected: {len(report['rejected'])} | duplicates: {len(report['duplicates'])}")
    for a in report["admitted"]:
        print("  +", a["paper_id"], a["origin"], a["questions"])
    for d in report["duplicates"]:
        print("  =", d["file"], "->", d["same_as"], f"({d['kind']})")


if __name__ == "__main__":
    main()
