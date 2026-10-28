"""Pure parsing of the Generate form's text fields into pipeline.run's bp_overrides dict — kept
separate from Flask so every edge case is a fast, direct function call, not a request round-trip.

This form is reachable over the internet once the app is hosted (not just from a trusted local CLI
user), so it also rejects out-of-range values that would let a visitor request an absurdly large
paper or an unapproved model, rather than passing them straight through to the solver/LLM."""
from src.webapp.catalog import CourseOption
from src.webapp.forms import ALLOWED_MODELS, build_overrides, validate_course_and_session, validate_model


def test_blank_form_produces_no_overrides_and_no_errors():
    overrides, errors = build_overrides({})
    assert overrides == {}
    assert errors == []


def test_sections_field_parses_into_section_specs():
    overrides, errors = build_overrides({"sections": "A:10x2,B:6x5:2"})
    assert errors == []
    specs = overrides["sections"]
    assert [(s.label, s.n_items, s.marks_each, s.n_choice) for s in specs] == [
        ("A", 10, 2.0, 0), ("B", 6, 5.0, 2),
    ]


def test_malformed_sections_field_reports_an_error_not_an_exception():
    overrides, errors = build_overrides({"sections": "not-a-valid-spec"})
    assert "sections" not in overrides
    assert len(errors) == 1
    assert "sections" in errors[0].lower()


def test_bloom_field_parses_level_to_share_mapping():
    overrides, errors = build_overrides({"bloom": "2:0.3,3:0.4,4:0.3"})
    assert errors == []
    assert overrides["bloom_target"] == {2: 0.3, 3: 0.4, 4: 0.3}


def test_bloom_field_accepts_L_prefixed_levels():
    overrides, errors = build_overrides({"bloom": "L2:0.5,L3:0.5"})
    assert errors == []
    assert overrides["bloom_target"] == {2: 0.5, 3: 0.5}


def test_malformed_bloom_field_reports_an_error():
    overrides, errors = build_overrides({"bloom": "garbage"})
    assert "bloom_target" not in overrides
    assert len(errors) == 1
    assert "bloom" in errors[0].lower()


def test_max_marks_and_duration_parse_as_integers():
    overrides, errors = build_overrides({"max_marks": "100", "duration": "180"})
    assert errors == []
    assert overrides["max_marks"] == 100
    assert overrides["duration_minutes"] == 180


def test_non_numeric_max_marks_reports_an_error():
    overrides, errors = build_overrides({"max_marks": "a lot"})
    assert "max_marks" not in overrides
    assert len(errors) == 1


def test_non_numeric_duration_reports_an_error():
    overrides, errors = build_overrides({"duration": "ages"})
    assert "duration_minutes" not in overrides
    assert len(errors) == 1


def test_multiple_bad_fields_report_multiple_errors():
    overrides, errors = build_overrides({"sections": "garbage", "bloom": "garbage"})
    assert len(errors) == 2


def test_max_marks_above_cap_reports_an_error():
    overrides, errors = build_overrides({"max_marks": "999999"})
    assert "max_marks" not in overrides
    assert len(errors) == 1


def test_max_marks_zero_or_negative_reports_an_error():
    overrides, errors = build_overrides({"max_marks": "0"})
    assert "max_marks" not in overrides
    assert len(errors) == 1


def test_duration_above_cap_reports_an_error():
    overrides, errors = build_overrides({"duration": "100000"})
    assert "duration_minutes" not in overrides
    assert len(errors) == 1


def test_sections_with_too_many_items_reports_an_error():
    overrides, errors = build_overrides({"sections": "A:10000x2"})
    assert "sections" not in overrides
    assert len(errors) == 1


def test_sections_with_too_many_sections_reports_an_error():
    spec = ",".join(f"S{i}:1x1" for i in range(20))
    overrides, errors = build_overrides({"sections": spec})
    assert "sections" not in overrides
    assert len(errors) == 1


def test_sections_with_choice_items_exceeding_total_items_reports_an_error():
    overrides, errors = build_overrides({"sections": "A:2x5:5"})
    assert "sections" not in overrides
    assert len(errors) == 1


def test_bloom_level_out_of_range_reports_an_error():
    overrides, errors = build_overrides({"bloom": "9:0.5,1:0.5"})
    assert "bloom_target" not in overrides
    assert len(errors) == 1


def test_bloom_share_out_of_range_reports_an_error():
    overrides, errors = build_overrides({"bloom": "2:1.5"})
    assert "bloom_target" not in overrides
    assert len(errors) == 1


def _courses():
    return [
        CourseOption("BCA202-3", "Operating Systems", "operating_systems"),
        CourseOption("BCA431", "Graph Theory", "graph_theory"),
    ]


def test_validate_course_and_session_accepts_a_known_course_code_and_a_clean_session():
    assert validate_course_and_session("BCA202-3", "November 2025", _courses()) == []


def test_validate_course_and_session_accepts_a_known_course_family():
    assert validate_course_and_session("graph_theory", "April 2026", _courses()) == []


def test_validate_course_and_session_rejects_an_unknown_course():
    errors = validate_course_and_session("DROP TABLE", "November 2025", _courses())
    assert len(errors) == 1


def test_validate_course_and_session_rejects_path_separators_in_session():
    errors = validate_course_and_session("BCA202-3", "../../etc", _courses())
    assert len(errors) == 1


def test_validate_course_and_session_rejects_an_overlong_session():
    errors = validate_course_and_session("BCA202-3", "x" * 60, _courses())
    assert len(errors) == 1


def test_validate_model_accepts_the_default_allowed_model():
    assert validate_model(next(iter(ALLOWED_MODELS))) == []


def test_validate_model_rejects_an_unapproved_model():
    assert len(validate_model("some-other-model:latest")) == 1
