"""Phase-0 entry point: run the dataset inventory over data/raw/ (master-prompt §8, §73 Phase A).

Usage:
    .venv/Scripts/python.exe scripts/prepare_data.py

Does NOT annotate, label, or train anything — this is the inventory/manifest step only. It is safe
to run repeatedly as new files are dropped into data/raw/ (idempotent — see
tests/test_dataset_version.py): it overwrites data/dataset_manifest.csv with a fresh scan each time,
and appends to data/dataset_versions.json only when the file set actually changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.dataset_version import record_dataset_version  # noqa: E402
from src.ingestion.manifest import Origin, build_manifest, write_manifest_csv  # noqa: E402
from src.ingestion.ocr import DEFAULT_PROVIDER  # noqa: E402


def main() -> None:
    config_path = REPO_ROOT / "configs" / "dataset.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    raw_dir = REPO_ROOT / config["paths"]["raw_dir"]
    manifest_path = REPO_ROOT / config["paths"]["manifest_csv"]
    versions_log_path = REPO_ROOT / config["paths"]["dataset_versions_log"]

    raw_dir.mkdir(parents=True, exist_ok=True)

    files = [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if not files:
        print(f"No source documents found in {raw_dir}.")
        print("Drop historical question papers (.pdf / .docx / .txt) into that directory and re-run.")
        return

    # Real institutional papers dropped into data/raw/ are always origin=REAL — fixture/synthetic
    # data lives under tests/fixtures/ and is never scanned by this script (Phase 0.5 §14).
    rows = build_manifest(raw_dir, origin=Origin.REAL)
    write_manifest_csv(rows, manifest_path)
    version = record_dataset_version(rows, versions_log_path)

    valid = [r for r in rows if r.is_valid]
    invalid = [r for r in rows if not r.is_valid]
    scanned = [r for r in valid if r.scanned_or_text == "scanned"]
    mixed = [r for r in valid if r.scanned_or_text == "mixed"]
    duplicates = [r for r in rows if r.duplicate_of is not None]

    print(f"Scanned {len(rows)} file(s) in {raw_dir}")
    print(f"  valid: {len(valid)}, invalid: {len(invalid)}")
    print(f"  scanned (needs OCR): {len(scanned)}, mixed: {len(mixed)}")
    if duplicates:
        print(f"  duplicate content detected: {len(duplicates)} file(s) — see 'duplicate_of' column")
    print(f"Manifest written to {manifest_path}")
    print(f"Dataset version: {version.version_id} "
          f"(first seen {version.created_at}; {version.valid_count} valid / {version.file_count} total)")

    if invalid:
        print("\nInvalid files:")
        for row in invalid:
            print(f"  - {row.filename}: {row.validation_errors}")

    if duplicates:
        print("\nDuplicate content (same sha256 as an earlier file):")
        for row in duplicates:
            print(f"  - {row.filename} is a duplicate of {row.duplicate_of}")

    if (scanned or mixed) and not DEFAULT_PROVIDER.is_available():
        print(
            "\nWARNING: some documents need OCR but no OCR provider is currently available. "
            "See docs/ENVIRONMENT_AUDIT.md §5 before processing these files further."
        )

    print(
        "\nNext step: run the data-quality gate (scripts/run_quality_gate.py) before any "
        "annotation or training begins."
    )


if __name__ == "__main__":
    main()
