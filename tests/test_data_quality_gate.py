"""Data-quality gate tests (Phase 0.5 §11/§13). Runs the gate against the real repo config
(configs/quality_gate.yaml) and against synthetic manifests/questions — never against a fabricated
"real" dataset, since none exists yet (Phase 0.5 §14: fixtures are always origin=FIXTURE)."""

from pathlib import Path

import pytest

from src.evaluation.data_quality.gate import (
    DatasetNotReadyError,
    Severity,
    assert_dataset_ready,
    load_thresholds,
    run_quality_gate,
)
from src.evaluation.data_quality.metrics import compute_quality_metrics
from src.extraction.engine import QuestionExtractor
from src.ingestion.loaders import load_document
from src.ingestion.manifest import Origin, build_manifest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def _thresholds():
    return load_thresholds(REPO_ROOT / "configs" / "quality_gate.yaml")


def test_thresholds_yaml_loads_and_has_expected_sections():
    thresholds = _thresholds()
    assert "blocking" in thresholds
    assert "warning" in thresholds
    assert thresholds["blocking"]["min_documents"] >= 1


def test_empty_dataset_fails_gate_with_no_documents_blocking_issue():
    metrics = compute_quality_metrics(manifest_rows=[], questions=[])
    result = run_quality_gate(metrics, _thresholds())
    assert result.status == "FAILED"
    codes = {i.code for i in result.blocking_issues}
    assert "no_documents" in codes


def test_metrics_computation_does_not_crash_on_empty_input():
    metrics = compute_quality_metrics(manifest_rows=[])
    assert metrics.document_count == 0
    assert metrics.extraction_success_rate == 0.0
    assert metrics.missing_marks_rate == 0.0


def test_real_fixture_set_produces_measured_metrics_end_to_end():
    rows = build_manifest(FIXTURES, origin=Origin.FIXTURE)
    valid_rows = [r for r in rows if r.is_valid]
    all_questions = []
    for row in valid_rows:
        doc = load_document(Path(row.source))
        all_questions.extend(QuestionExtractor().extract(doc))

    metrics = compute_quality_metrics(rows, all_questions)
    assert metrics.document_count == len(rows)
    assert metrics.question_count == len(all_questions)
    assert metrics.question_count > 0
    assert 0.0 <= metrics.marks_extraction_rate <= 1.0

    result = run_quality_gate(metrics, _thresholds())
    # Fixtures have plenty of questions and reasonable extraction, but no subject/year metadata
    # by design (§8 — never fabricated), so we expect WARNING issues but not necessarily FAILED
    # on document/question counts specifically.
    assert result.status in {"PASSED", "FAILED"}
    assert any(i.code == "high_missing_subject_rate" for i in result.warnings)


def test_gate_result_blocks_when_zero_questions_extracted_despite_valid_documents():
    from src.ingestion.manifest import ManifestRow
    row = ManifestRow(
        document_id="abc", filename="empty_prose.txt", format="txt", size_bytes=100,
        sha256="abc", origin="fixture", academic_year=None, program=None, semester=None,
        course=None, subject=None, source="x", file_modified_at=None, page_count=1,
        scanned_or_text="text", pages_needing_ocr=0, extraction_quality=1.0,
        processing_status="valid", is_valid=True, validation_errors="", duplicate_of=None,
    )
    metrics = compute_quality_metrics([row], questions=[])
    result = run_quality_gate(metrics, _thresholds())
    assert result.status == "FAILED"
    assert "no_questions_extracted" in {i.code for i in result.blocking_issues}


# --- training blocker ---

def test_assert_dataset_ready_raises_on_failed_gate_without_override():
    metrics = compute_quality_metrics(manifest_rows=[], questions=[])
    result = run_quality_gate(metrics, _thresholds())
    with pytest.raises(DatasetNotReadyError):
        assert_dataset_ready(result)


def test_assert_dataset_ready_allows_override_but_does_not_raise(capsys):
    metrics = compute_quality_metrics(manifest_rows=[], questions=[])
    result = run_quality_gate(metrics, _thresholds())
    assert_dataset_ready(result, allow_unsafe=True)  # must not raise
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "override" in captured.out.lower()


def test_assert_dataset_ready_passthrough_when_gate_passed():
    from src.evaluation.data_quality.gate import Issue, QualityGateResult
    passed_result = QualityGateResult(status="PASSED", issues=[Issue(Severity.INFO, "ok", "fine")])
    assert_dataset_ready(passed_result)  # must not raise, no override needed
