"""Data-quality gate (master-prompt §13, Phase 0.5 §11/§13).

Turns `QualityMetrics` into a set of severity-tagged issues and an overall PASSED/FAILED status.
Deliberately does NOT compute a single composite numeric "quality score" — the instructions for this
phase are explicit that arbitrary scoring is premature; a gate built from named, individually
justified threshold checks is more auditable and lets each check's rationale be inspected on its own.

`assert_dataset_ready()` is the training blocker (§13): any future training script must call this
before proceeding, and it raises unless the gate passed or the caller explicitly opts into an unsafe
override (loudly logged, never silent).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from src.evaluation.data_quality.metrics import QualityMetrics


class Severity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Issue:
    severity: Severity
    code: str
    message: str


@dataclass
class QualityGateResult:
    status: str  # "PASSED" | "FAILED"
    issues: list[Issue] = field(default_factory=list)
    metrics: QualityMetrics | None = None

    @property
    def blocking_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.BLOCKING]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]


def load_thresholds(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_quality_gate(metrics: QualityMetrics, thresholds: dict[str, Any]) -> QualityGateResult:
    issues: list[Issue] = []
    b = thresholds.get("blocking", {})
    w = thresholds.get("warning", {})

    # --- blocking checks ---
    if metrics.document_count < b.get("min_documents", 1):
        issues.append(Issue(Severity.BLOCKING, "no_documents",
                             f"No documents found (0 < required minimum {b.get('min_documents', 1)})."))
    elif metrics.extraction_success_rate < b.get("min_valid_extraction_success_rate", 0.5):
        issues.append(Issue(
            Severity.BLOCKING, "extraction_success_too_low",
            f"Extraction success rate {metrics.extraction_success_rate:.1%} is below the blocking "
            f"minimum {b.get('min_valid_extraction_success_rate', 0.5):.1%}.",
        ))

    if metrics.document_count > 0 and metrics.question_count < b.get("min_questions", 1):
        issues.append(Issue(
            Severity.BLOCKING, "no_questions_extracted",
            f"{metrics.valid_document_count} valid document(s) but 0 questions were extracted - "
            "the extraction engine may not recognize this paper's numbering format.",
        ))

    # --- warning checks (never block, but must be visible) ---
    if metrics.document_count > 0 and metrics.extraction_success_rate < w.get("min_extraction_success_rate", 0.9):
        issues.append(Issue(
            Severity.WARNING, "extraction_success_below_target",
            f"Extraction success rate {metrics.extraction_success_rate:.1%} is below the target "
            f"{w.get('min_extraction_success_rate', 0.9):.1%}.",
        ))
    if metrics.question_count > 0 and metrics.missing_marks_rate > w.get("max_missing_marks_rate", 0.3):
        issues.append(Issue(
            Severity.WARNING, "high_missing_marks_rate",
            f"{metrics.missing_marks_rate:.1%} of extracted questions have no detected marks.",
        ))
    if metrics.document_count > 0 and metrics.missing_subject_rate > w.get("max_missing_subject_rate", 0.5):
        issues.append(Issue(
            Severity.WARNING, "high_missing_subject_rate",
            f"{metrics.missing_subject_rate:.1%} of documents have no subject metadata - "
            "confirm a filename/metadata convention with the source institution.",
        ))
    if metrics.document_count > 0 and metrics.missing_academic_year_rate > w.get("max_missing_academic_year_rate", 0.5):
        issues.append(Issue(
            Severity.WARNING, "high_missing_academic_year_rate",
            f"{metrics.missing_academic_year_rate:.1%} of documents have no academic-year metadata.",
        ))
    if metrics.exact_document_duplicate_rate > w.get("max_exact_document_duplicate_rate", 0.05):
        issues.append(Issue(
            Severity.WARNING, "exact_duplicate_documents",
            f"{metrics.exact_document_duplicate_rate:.1%} of documents are byte-identical duplicates "
            "of another document already in the set.",
        ))
    if metrics.question_count > 0 and metrics.mean_extraction_confidence < w.get("min_mean_extraction_confidence", 0.7):
        issues.append(Issue(
            Severity.WARNING, "low_mean_extraction_confidence",
            f"Mean extraction confidence {metrics.mean_extraction_confidence:.2f} is below target "
            f"{w.get('min_mean_extraction_confidence', 0.7):.2f}.",
        ))
    scanned_rate = metrics.scanned_or_text_distribution.get("scanned", 0) + \
        metrics.scanned_or_text_distribution.get("mixed", 0)
    scanned_rate = scanned_rate / metrics.document_count if metrics.document_count else 0.0
    if scanned_rate > w.get("max_scanned_document_rate", 0.3):
        issues.append(Issue(
            Severity.WARNING, "high_scanned_document_rate",
            f"{scanned_rate:.1%} of documents need OCR - see docs/ENVIRONMENT_AUDIT.md for OCR "
            "readiness before these can be fully processed.",
        ))

    # --- informational, always-visible context ---
    issues.append(Issue(
        Severity.INFO, "label_readiness",
        f"unit={metrics.unit_coverage_rate:.0%} topic={metrics.topic_coverage_rate:.0%} "
        f"bloom={metrics.bloom_coverage_rate:.0%} dok={metrics.dok_coverage_rate:.0%} coverage - "
        "expected to be 0% pre-annotation; not itself a blocker at this phase.",
    ))

    status = "FAILED" if any(i.severity == Severity.BLOCKING for i in issues) else "PASSED"
    return QualityGateResult(status=status, issues=issues, metrics=metrics)


class DatasetNotReadyError(RuntimeError):
    """Raised by assert_dataset_ready() when the quality gate failed and no override was given."""


def assert_dataset_ready(result: QualityGateResult, allow_unsafe: bool = False) -> None:
    """The training blocker (Phase 0.5 §13). Call this at the top of every future training script.

    Raises DatasetNotReadyError if the gate failed, UNLESS allow_unsafe=True (wired to a CLI flag
    such as --allow-unsafe-dataset), in which case it logs a loud, unmissable warning and returns
    instead of raising.
    """
    if result.status == "PASSED":
        return

    blocking_summary = "; ".join(f"[{i.code}] {i.message}" for i in result.blocking_issues)
    if not allow_unsafe:
        raise DatasetNotReadyError(
            f"Dataset failed the quality gate - training is blocked. Blocking issues: {blocking_summary}"
        )

    print("=" * 80)
    print("WARNING: --allow-unsafe-dataset override in effect.")
    print("Proceeding DESPITE a FAILED data-quality gate. This is a research safety override, not")
    print("a fix - results produced this way must be reported as such, never as validated research.")
    print(f"Blocking issues bypassed: {blocking_summary}")
    print("=" * 80)
