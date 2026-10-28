"""Read-only views over the project's existing data files for the web app: the real course list for
the Generate form (no hand-typed course codes that might not exist) and the real list of already
generated papers for the Papers Library. Never writes; the filesystem under data/ and outputs/ stays
the single source of truth the CLI also uses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CourseOption:
    code: str
    name: str
    family: str


def list_courses(papers_path: Path) -> list[CourseOption]:
    if not papers_path.exists():
        return []
    seen: dict[str, CourseOption] = {}
    for line in papers_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        seen.setdefault(p["course_code"], CourseOption(p["course_code"], p["course_name"], p["course_family"]))
    return sorted(seen.values(), key=lambda c: c.code)


@dataclass
class PaperEntry:
    course_code: str
    exam_session: str
    version: int
    approvable: bool
    generated_at: float
    dir: str


def list_generated_papers(out_root: Path) -> list[PaperEntry]:
    if not out_root.exists():
        return []
    entries: list[PaperEntry] = []
    for meta_path in out_root.glob("*/v*/paper.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entries.append(PaperEntry(
            course_code=data.get("course_code", "?"),
            exam_session=data.get("exam_session", "?"),
            version=data.get("version", 0),
            approvable=bool((data.get("validation") or {}).get("approvable")),
            generated_at=meta_path.stat().st_mtime,
            dir=meta_path.parent.relative_to(out_root).as_posix(),
        ))
    entries.sort(key=lambda e: e.generated_at, reverse=True)
    return entries
