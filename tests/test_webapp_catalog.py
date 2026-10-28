"""Catalog helpers: the real course list for the Generate form (from data/processed/papers.jsonl)
and the real list of already-generated papers for the Papers Library (from outputs/papers/)."""
import json

from src.webapp.catalog import list_courses, list_generated_papers


def write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def test_list_courses_distinct_sorted(tmp_path):
    p = tmp_path / "papers.jsonl"
    write_jsonl(p, [
        {"course_code": "BCA202-3", "course_name": "Operating Systems", "course_family": "operating_systems"},
        {"course_code": "BCA431", "course_name": "Graph Theory", "course_family": "graph_theory"},
        {"course_code": "BCA202-3", "course_name": "Operating Systems", "course_family": "operating_systems"},
    ])
    courses = list_courses(p)
    assert [c.code for c in courses] == ["BCA202-3", "BCA431"]
    assert courses[0].name == "Operating Systems"
    assert courses[0].family == "operating_systems"


def test_list_courses_missing_file_returns_empty(tmp_path):
    assert list_courses(tmp_path / "does_not_exist.jsonl") == []


def test_list_generated_papers_reads_metadata_newest_first(tmp_path):
    out_root = tmp_path / "papers"
    older = out_root / "BCA202-3_November2025" / "v1"
    newer = out_root / "BCA431_April2026" / "v1"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "paper.json").write_text(json.dumps({
        "course_code": "BCA202-3", "exam_session": "November 2025", "version": 1,
        "validation": {"approvable": True},
    }), encoding="utf-8")
    (newer / "paper.json").write_text(json.dumps({
        "course_code": "BCA431", "exam_session": "April 2026", "version": 1,
        "validation": {"approvable": False},
    }), encoding="utf-8")
    import os
    import time
    now = time.time()
    os.utime(older / "paper.json", (now - 100, now - 100))
    os.utime(newer / "paper.json", (now, now))

    entries = list_generated_papers(out_root)
    assert [e.course_code for e in entries] == ["BCA431", "BCA202-3"]
    assert entries[0].approvable is False
    assert entries[1].approvable is True
    assert entries[1].dir == older.relative_to(out_root).as_posix()


def test_list_generated_papers_missing_root_returns_empty(tmp_path):
    assert list_generated_papers(tmp_path / "nope") == []


def test_list_generated_papers_skips_unreadable_metadata(tmp_path):
    out_root = tmp_path / "papers"
    bad = out_root / "BCA999-1_May2026" / "v1"
    bad.mkdir(parents=True)
    (bad / "paper.json").write_text("not json", encoding="utf-8")
    assert list_generated_papers(out_root) == []
