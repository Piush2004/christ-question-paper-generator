"""Data-quality gate CLI (master-prompt §13, Phase 0.5 §11/§13).

Usage:
    .venv/Scripts/python.exe scripts/run_quality_gate.py
    .venv/Scripts/python.exe scripts/run_quality_gate.py --allow-unsafe-dataset

Runs the manifest scan + question extraction over data/raw/, computes quality metrics, and applies
the gate (configs/quality_gate.yaml). Exits non-zero if the gate fails, UNLESS --allow-unsafe-dataset
is passed — that flag never suppresses the warning output, it only prevents the hard exit, and its
use is loudly logged (never silent) per the training-blocker design in
src/evaluation/data_quality/gate.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.evaluation.data_quality.gate import (  # noqa: E402
    DatasetNotReadyError,
    assert_dataset_ready,
    load_thresholds,
    run_quality_gate,
)
from src.evaluation.data_quality.metrics import compute_quality_metrics  # noqa: E402
from src.extraction.engine import QuestionExtractor  # noqa: E402
from src.ingestion.loaders import load_document  # noqa: E402
from src.ingestion.manifest import Origin, build_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-unsafe-dataset", action="store_true",
        help="Proceed even if the quality gate fails. Loudly logged; never use silently.",
    )
    parser.add_argument(
        "--raw-dir", default=None,
        help="Override the raw document directory (defaults to configs/dataset.yaml's raw_dir).",
    )
    args = parser.parse_args()

    dataset_config = yaml.safe_load((REPO_ROOT / "configs" / "dataset.yaml").read_text(encoding="utf-8"))
    raw_dir = Path(args.raw_dir) if args.raw_dir else REPO_ROOT / dataset_config["paths"]["raw_dir"]
    thresholds = load_thresholds(REPO_ROOT / "configs" / "quality_gate.yaml")

    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = build_manifest(raw_dir, origin=Origin.REAL)
    valid_rows = [r for r in rows if r.is_valid]

    questions = []
    for row in valid_rows:
        doc = load_document(Path(row.source))
        questions.extend(QuestionExtractor().extract(doc))

    metrics = compute_quality_metrics(rows, questions)
    result = run_quality_gate(metrics, thresholds)

    print(f"Dataset quality gate: {result.status}")
    print(f"  documents: {metrics.document_count} ({metrics.valid_document_count} valid)")
    print(f"  questions extracted: {metrics.question_count}")
    print(f"  extraction success rate: {metrics.extraction_success_rate:.1%}")
    print()
    for issue in result.blocking_issues:
        print(f"  [BLOCKING] {issue.code}: {issue.message}")
    for issue in result.warnings:
        print(f"  [WARNING]  {issue.code}: {issue.message}")
    for issue in [i for i in result.issues if i.severity.value == "INFO"]:
        print(f"  [INFO]     {issue.code}: {issue.message}")

    try:
        assert_dataset_ready(result, allow_unsafe=args.allow_unsafe_dataset)
    except DatasetNotReadyError as exc:
        print(f"\n{exc}")
        return 1

    print("\nDataset is ready for the next phase (annotation)." if result.status == "PASSED"
          else "\nProceeding under --allow-unsafe-dataset override — see warnings above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
