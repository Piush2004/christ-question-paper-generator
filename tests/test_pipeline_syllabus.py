"""history_for() auto-loading data/processed/syllabus.json when present, never crashing when absent."""
import json

from src.generation.blueprint import load_papers, load_questions
from src.generation.pipeline import history_for


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
