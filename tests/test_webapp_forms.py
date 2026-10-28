"""Pure parsing of the Generate form's text fields into pipeline.run's bp_overrides dict — kept
separate from Flask so every edge case is a fast, direct function call, not a request round-trip."""
from src.webapp.forms import build_overrides


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
