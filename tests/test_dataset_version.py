"""Dataset versioning + idempotency tests (Phase 0.5 §8/§9)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from src.ingestion.dataset_version import compute_dataset_version, record_dataset_version
from src.ingestion.manifest import Origin, build_manifest

FIXTURES = Path(__file__).parent / "fixtures"


def test_running_manifest_build_twice_is_idempotent():
    rows_run1 = build_manifest(FIXTURES, origin=Origin.FIXTURE)
    rows_run2 = build_manifest(FIXTURES, origin=Origin.FIXTURE)

    assert len(rows_run1) == len(rows_run2)
    assert [r.sha256 for r in rows_run1] == [r.sha256 for r in rows_run2]
    assert [r.document_id for r in rows_run1] == [r.document_id for r in rows_run2]
    assert compute_dataset_version(rows_run1) == compute_dataset_version(rows_run2)


def test_dataset_version_changes_when_a_file_is_added(tmp_path: Path):
    (tmp_path / "paper1.txt").write_text("Q1. Something. [5]\n")
    rows_before = build_manifest(tmp_path, origin=Origin.FIXTURE)
    version_before = compute_dataset_version(rows_before)

    (tmp_path / "paper2.txt").write_text("Q1. Something else. [5]\n")
    rows_after = build_manifest(tmp_path, origin=Origin.FIXTURE)
    version_after = compute_dataset_version(rows_after)

    assert version_before != version_after


def test_dataset_version_stable_regardless_of_scan_order(tmp_path: Path):
    (tmp_path / "a.txt").write_text("Q1. A. [5]\n")
    (tmp_path / "b.txt").write_text("Q1. B. [5]\n")
    rows = build_manifest(tmp_path, origin=Origin.FIXTURE)
    reversed_rows = list(reversed(rows))
    assert compute_dataset_version(rows) == compute_dataset_version(reversed_rows)


def test_record_dataset_version_is_append_only_and_deduped(tmp_path: Path):
    versions_path = tmp_path / "dataset_versions.json"
    rows = build_manifest(FIXTURES, origin=Origin.FIXTURE)
    fixed_time = datetime(2026, 8, 18, tzinfo=UTC)

    record1 = record_dataset_version(rows, versions_path, now=fixed_time)
    record2 = record_dataset_version(rows, versions_path, now=fixed_time)  # same content, run again

    assert record1.version_id == record2.version_id
    assert record1.created_at == record2.created_at  # not overwritten on the second run

    history = json.loads(versions_path.read_text(encoding="utf-8"))
    assert len(history) == 1  # deduped, not appended twice


def test_record_dataset_version_appends_new_entry_for_new_content(tmp_path: Path):
    versions_path = tmp_path / "dataset_versions.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.txt").write_text("Q1. A. [5]\n")

    rows_v1 = build_manifest(data_dir, origin=Origin.FIXTURE)
    record_dataset_version(rows_v1, versions_path)

    (data_dir / "b.txt").write_text("Q1. B. [5]\n")
    rows_v2 = build_manifest(data_dir, origin=Origin.FIXTURE)
    record_dataset_version(rows_v2, versions_path)

    history = json.loads(versions_path.read_text(encoding="utf-8"))
    assert len(history) == 2
