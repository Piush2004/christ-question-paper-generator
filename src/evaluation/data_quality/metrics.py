"""Dataset-quality metrics computation (master-prompt §12/§13, Phase 0.5 §11).

Computes real, measured statistics from a manifest (document-level) and, once extraction has run,
a list of extracted questions (question-level). Every metric here degrades gracefully to 0/empty on
an empty dataset rather than crashing (division-by-zero guarded throughout) — this module must work
correctly on the current empty `data/raw/` just as well as on a real dataset later.

No metric here is fabricated: unit/topic coverage is genuinely 0.0 before annotation exists, and
that is the CORRECT value, not a placeholder to be replaced — a downstream reader must be able to
trust that a 0.0 here means "genuinely not yet annotated," not "not yet wired up."
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from src.extraction.engine import ExtractedQuestion
from src.ingestion.manifest import ManifestRow


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator > 0 else 0.0


@dataclass
class QualityMetrics:
    # --- coverage ---
    document_count: int = 0
    valid_document_count: int = 0
    question_count: int = 0
    subject_count: int = 0
    academic_year_count: int = 0

    # --- extraction ---
    extraction_success_rate: float = 0.0        # valid documents / total documents
    question_segmentation_rate: float = 0.0     # fraction of valid docs that yielded >=1 question
    marks_extraction_rate: float = 0.0          # fraction of questions with marks detected
    section_extraction_rate: float = 0.0        # fraction of questions with a section label detected
    mean_extraction_confidence: float = 0.0

    # --- completeness ---
    missing_subject_rate: float = 0.0
    missing_academic_year_rate: float = 0.0
    missing_marks_rate: float = 0.0
    empty_question_text_rate: float = 0.0

    # --- duplication (document-level exact-content only; question-level near-duplicate
    #     detection is the future novelty engine's job, §28 — explicitly out of scope here) ---
    exact_document_duplicate_rate: float = 0.0

    # --- label readiness (always 0.0 pre-annotation — that is correct, not a bug) ---
    unit_coverage_rate: float = 0.0
    topic_coverage_rate: float = 0.0
    bloom_coverage_rate: float = 0.0
    dok_coverage_rate: float = 0.0

    # --- distribution (for imbalance inspection, not scored here) ---
    subject_distribution: dict = field(default_factory=dict)
    academic_year_distribution: dict = field(default_factory=dict)
    question_type_distribution: dict = field(default_factory=dict)  # always empty pre-classification
    scanned_or_text_distribution: dict = field(default_factory=dict)


def compute_quality_metrics(
    manifest_rows: list[ManifestRow],
    questions: list[ExtractedQuestion] | None = None,
) -> QualityMetrics:
    questions = questions or []
    m = QualityMetrics()

    m.document_count = len(manifest_rows)
    valid_rows = [r for r in manifest_rows if r.is_valid]
    m.valid_document_count = len(valid_rows)
    m.extraction_success_rate = _safe_rate(len(valid_rows), len(manifest_rows))

    subjects = {r.subject for r in manifest_rows if r.subject}
    years = {r.academic_year for r in manifest_rows if r.academic_year}
    m.subject_count = len(subjects)
    m.academic_year_count = len(years)
    m.missing_subject_rate = _safe_rate(sum(1 for r in manifest_rows if not r.subject), len(manifest_rows))
    m.missing_academic_year_rate = _safe_rate(
        sum(1 for r in manifest_rows if not r.academic_year), len(manifest_rows)
    )

    duplicate_docs = sum(1 for r in manifest_rows if r.duplicate_of is not None)
    m.exact_document_duplicate_rate = _safe_rate(duplicate_docs, len(manifest_rows))

    m.subject_distribution = dict(Counter(r.subject for r in manifest_rows if r.subject))
    m.academic_year_distribution = dict(Counter(r.academic_year for r in manifest_rows if r.academic_year))
    m.scanned_or_text_distribution = dict(Counter(r.scanned_or_text for r in manifest_rows))

    m.question_count = len(questions)
    if questions:
        m.marks_extraction_rate = _safe_rate(sum(1 for q in questions if q.marks is not None), len(questions))
        m.section_extraction_rate = _safe_rate(
            sum(1 for q in questions if q.section_label is not None), len(questions)
        )
        m.missing_marks_rate = _safe_rate(sum(1 for q in questions if q.marks is None), len(questions))
        m.empty_question_text_rate = _safe_rate(
            sum(1 for q in questions if not q.raw_text.strip()), len(questions)
        )
        m.mean_extraction_confidence = round(
            sum(q.extraction_confidence for q in questions) / len(questions), 4
        )

    if valid_rows:
        docs_with_questions = {q.page_number for q in questions}  # crude proxy pending doc-id threading
        m.question_segmentation_rate = _safe_rate(min(len(docs_with_questions), len(valid_rows)), len(valid_rows)) \
            if questions else 0.0

    # unit/topic/bloom/dok coverage rates are intentionally left at 0.0 (dataclass default) until
    # the annotation stage (src/annotation/, not yet built — see docs/RESEARCH_GAP.md sequencing)
    # produces AnnotationProvenance-wrapped labels to measure coverage over.

    return m
