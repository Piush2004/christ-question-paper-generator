"""Syllabus-grounded topic clusters in build_history(), and the unsupervised fallback when absent."""
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
