"""Deterministic paper validator: each hard rule must fire on a deliberately broken synthetic paper."""
from src.generation.blueprint import Blueprint, SectionSpec
from src.generation.render import PaperQuestion
from src.generation.validate import summarize, validate_paper


def bp():
    return Blueprint(course_code="T1", course_name="TEST", semester=1, exam_session="November 2025", max_marks=14,
                     duration_minutes=60, outcomes={"CO1": "alpha", "CO2": "beta"},
                     sections=[SectionSpec("A", 2, 2), SectionSpec("B", 2, 5, 1)])


def good():
    return [
        PaperQuestion("A", 1, None, "Define the term kernel in an operating system and state its role.", 2, "CO1", 1),
        PaperQuestion("A", 2, None, "State two advantages of using virtual memory in modern computers.", 2, "CO2", 1),
        PaperQuestion("B", 3, "a", "Explain how a process control block is used during a context switch in detail.", 5, "CO1", 2),
        PaperQuestion("B", 3, "b", "Describe the working of the round robin scheduling algorithm with a small example.", 5, "CO1", 2),
        PaperQuestion("B", 4, None, "Compare paging and segmentation as memory management techniques with examples.", 5, "CO2", 2),
    ]


def failed(checks):
    return {c.name for c in checks if not c.passed}


def test_valid_paper_passes_all_hard_checks():
    s = summarize(validate_paper(bp(), good()))
    assert s["approvable"], s["hard_failures"]


def test_wrong_marks_total_and_item_count_detected():
    qs = good()[:-1]
    f = failed(validate_paper(bp(), qs))
    assert {"items_per_section", "total_marks"} <= f


def test_missing_course_outcome_detected():
    qs = good()
    qs[1] = PaperQuestion("A", 2, None, qs[1].text, 2, "CO1", 1)
    qs[4] = PaperQuestion("B", 4, None, qs[4].text, 5, "CO1", 2)
    assert "all_course_outcomes_covered" in failed(validate_paper(bp(), qs))


def test_dangling_figure_reference_and_short_text_detected():
    qs = good()
    qs[0] = PaperQuestion("A", 1, None, "Explain the process shown in the following diagram clearly.", 2, "CO1", 1)
    qs[1] = PaperQuestion("A", 2, None, "Define.", 2, "CO2", 1)
    f = failed(validate_paper(bp(), qs))
    assert "self_contained" in f and "question_length" in f


def test_duplicate_questions_within_paper_detected():
    qs = good()
    qs[4] = PaperQuestion("B", 4, None, qs[2].text, 5, "CO2", 2)
    assert "no_duplicates_within_paper" in failed(validate_paper(bp(), qs))


def test_copy_of_history_detected():
    from src.embeddings.encoder import encode
    qs = good()
    hist = [qs[0].text, "Something totally unrelated about cooking pasta."]
    assert "not_copied_from_history" in failed(validate_paper(bp(), qs, hist, encode(hist)))


def test_or_alternatives_must_share_outcome_and_level():
    qs = good()
    qs[3] = PaperQuestion("B", 3, "b", qs[3].text, 5, "CO2", 3)
    assert "alternatives_same_outcome_level" in failed(validate_paper(bp(), qs))


def test_question_ending_with_colon_or_pointing_at_missing_data_is_flagged():
    from src.generation.generator import _FIGURE_REF
    assert _FIGURE_REF.search("Calculate the shortest path from City A to City F given the following road network data:")
    assert _FIGURE_REF.search("Using Dijkstra's algorithm, find the distances as follows:")
    assert _FIGURE_REF.search("Refer to the figure and find the area.")
    assert not _FIGURE_REF.search("Explain how Dijkstra's algorithm finds shortest paths in a weighted graph with an example.")
    assert not _FIGURE_REF.search("Find the shortest path from A to F where edges are A-B 4, B-F 3, A-F 9.")


def test_constraint_provenance_separates_hard_soft_and_preference():
    from types import SimpleNamespace as NS
    from src.generation.pipeline import constraint_provenance
    prof = NS(clusters=[NS(label="trees, spanning")])
    it = NS(cluster=0)
    with_target = Blueprint(course_code="T", course_name="T", semester=1, exam_session="x", max_marks=4, duration_minutes=60,
                            outcomes={"CO1": "a"}, sections=[SectionSpec("A", 2, 2)], bloom_target={2: 1.0})
    p = constraint_provenance(with_target, prof, it)
    assert p["section_structure_and_marks"].startswith("HARD") and p["rbt_level"].startswith("SOFT target — teacher")
    assert p["topic"].startswith("PREFERENCE") and "NOT a verified syllabus topic" in p["topic"]
    assert "historical marks" in constraint_provenance(
        Blueprint(**{**with_target.__dict__, "bloom_target": None}), prof, it)["rbt_level"]


def test_constraint_provenance_reports_syllabus_grounded_topic_when_available():
    from types import SimpleNamespace as NS
    from src.generation.pipeline import constraint_provenance
    prof = NS(clusters=[NS(label="Process Management")], topics_source="syllabus")
    it = NS(cluster=0)
    bp = Blueprint(course_code="T", course_name="T", semester=1, exam_session="x", max_marks=4, duration_minutes=60,
                   outcomes={"CO1": "a"}, sections=[SectionSpec("A", 2, 2)])
    p = constraint_provenance(bp, prof, it)
    assert p["topic"].startswith("SOFT") and "verified syllabus unit" in p["topic"] and "Process Management" in p["topic"]
