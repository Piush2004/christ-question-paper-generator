"""Canonical question record schema (master-prompt §11).

Design choice: every soft/inferred label (unit, topic, difficulty, bloom, dok, question_type) is
wrapped in `AnnotationProvenance` rather than stored as a bare value. This is not optional scaffolding
— master-prompt §14 requires every label to carry provenance (source + confidence +
teacher_verified), because historical papers do not arrive with these labels attached; they are always
inferred, and an un-traceable inferred label is scientifically unusable (§29, §77: no claim without
evidence). `raw_text` is kept separately from `question_text` (normalized) because §9 forbids
destroying the original source.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class LabelSource(StrEnum):
    """How a label's value was produced. This is deliberately a flat, closed set (Phase 0.5 §6) so
    every downstream consumer can branch on it without guessing:

    - RAW: the value is the literal source content, not inferred at all (e.g. would apply to
      question_text/raw_text if they were ever wrapped in provenance — they currently aren't,
      because their provenance is already fully captured by `extraction_method` +
      `extraction_confidence` at the record level; RAW exists here for fields like `marks` that
      are sometimes stated unambiguously and verbatim rather than pattern-matched).
    - RULE_INFERRED: produced by a deterministic rule/regex/heuristic (e.g. marks parsed from a
      "[10]" pattern, unit/topic from keyword or syllabus-string matching).
    - MODEL_PREDICTED: produced by a classical ML model or embedding-similarity lookup.
    - LLM_PREDICTED: produced by an LLM call.
    - TEACHER_VERIFIED: a human confirmed an existing value's correctness without retyping it —
      use this when the *origin* of the underlying prediction is not itself worth preserving
      (e.g. bulk-imported legacy data already marked correct by a past reviewer). Prefer instead
      setting `teacher_verified=True` alongside the original RULE_INFERRED/MODEL_PREDICTED/
      LLM_PREDICTED source when that provenance IS worth keeping — which is the common case.
    - MANUALLY_ENTERED: a human typed the value from scratch; there was no prior prediction.
    """

    RAW = "raw"
    RULE_INFERRED = "rule_inferred"
    MODEL_PREDICTED = "model_predicted"
    LLM_PREDICTED = "llm_predicted"
    TEACHER_VERIFIED = "teacher_verified"
    MANUALLY_ENTERED = "manually_entered"


class QuestionType(StrEnum):
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    NUMERICAL = "numerical"
    DIAGRAM = "diagram"
    OTHER = "other"


class ExtractionMethod(StrEnum):
    TEXT = "text"
    OCR = "ocr"


class DataOrigin(StrEnum):
    """Mirrors src.ingestion.manifest.Origin's values (kept as an independent enum rather than an
    import so src/schemas has no dependency on src/ingestion — schemas is the generic layer other
    packages depend on, not the reverse). Phase 0.5 §14: this field exists so fixture/synthetic
    test data can never be silently mistaken for real institutional data by a downstream consumer
    that only sees Question objects, not the manifest they came from."""

    REAL = "real"
    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    EVALUATION = "evaluation"


class AnnotationProvenance(BaseModel, Generic[T]):
    """Wraps any inferred/annotated label with its source, confidence, and human-verification state."""

    value: T | None = None
    source: LabelSource | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    teacher_verified: bool = False
    annotator_id: str | None = None
    annotated_at: datetime | None = None

    def is_reliable(self, min_confidence: float = 0.7) -> bool:
        """A label counts as reliable if a human verified it, or its model confidence clears the bar."""
        if self.teacher_verified:
            return True
        return self.confidence is not None and self.confidence >= min_confidence


class Question(BaseModel):
    # --- identity & provenance (never inferred, always known at extraction time) ---
    question_id: str
    source_document: str
    source_file_hash: str
    source_page: int
    extraction_method: ExtractionMethod
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # --- original vs normalized text — original is never overwritten (§9) ---
    raw_text: str
    question_text: str

    # --- structural position within the source document ---
    section_label: str | None = None
    question_number_raw: str | None = None
    parent_question_id: str | None = None
    alternative_to_id: str | None = None
    # 0-indexed line offsets within the source document's flattened line stream (see
    # src/extraction/engine.py) — lets a researcher jump straight to the exact source location,
    # not just the page (Phase 0.5 §4: "source location where possible").
    source_line_start: int | None = None
    source_line_end: int | None = None

    # --- document-level metadata (usually filename-derived or manifest-provided, not inferred per-question) ---
    academic_year: str | None = None
    program: str | None = None
    semester: str | None = None
    course: str | None = None
    subject: str | None = None

    # --- dataset lifecycle (Phase 0.5 §8/§14) ---
    dataset_version: str | None = None  # content-hash version id of the ingest run this came from
    origin: DataOrigin = DataOrigin.REAL

    # --- curriculum mapping (inferred → provenance-wrapped) ---
    unit: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    topic: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    subtopic: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    learning_outcome: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)

    # --- question characterization (inferred → provenance-wrapped) ---
    question_type: AnnotationProvenance[QuestionType] = Field(default_factory=AnnotationProvenance)
    # marks is provenance-wrapped (not a bare float) because it is usually RULE_INFERRED via regex
    # over messy source formatting (see src/extraction/patterns.py) and is exactly the kind of
    # field a teacher may need to correct — losing that history would make later error analysis
    # (master-prompt §52) impossible.
    marks: AnnotationProvenance[float] = Field(default_factory=AnnotationProvenance)
    difficulty_class: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    difficulty_score: AnnotationProvenance[float] = Field(default_factory=AnnotationProvenance)
    course_outcome: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    bloom: AnnotationProvenance[str] = Field(default_factory=AnnotationProvenance)
    dok: AnnotationProvenance[int] = Field(default_factory=AnnotationProvenance)

    # --- representation ---
    embedding_model: str | None = None
    embedding: list[float] | None = None

    # --- dataset role ---
    gold_standard: bool = False
    split: str | None = None  # "train" | "val" | "test", assigned by leakage-safe splitter, not here

    model_config = ConfigDict(use_enum_values=False)
