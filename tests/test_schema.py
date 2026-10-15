"""Schema audit tests (Phase 0.5 §5/§6) — proves the pydantic model actually accepts and round-trips
a realistic record, not just that it imports."""

from src.schemas.question import (
    AnnotationProvenance,
    DataOrigin,
    ExtractionMethod,
    LabelSource,
    Question,
    QuestionType,
)


def test_minimal_question_constructs_with_defaults():
    q = Question(
        question_id="q-0001",
        source_document="2024_ML_endsem.pdf",
        source_file_hash="abc123",
        source_page=2,
        extraction_method=ExtractionMethod.TEXT,
        raw_text="1. Explain overfitting. [10]",
        question_text="Explain overfitting.",
    )
    assert q.origin == DataOrigin.REAL
    assert q.marks.value is None
    assert q.bloom.value is None
    assert q.gold_standard is False


def test_full_provenance_chain_round_trips():
    q = Question(
        question_id="q-0002",
        source_document="2024_ML_endsem.pdf",
        source_file_hash="abc123",
        source_page=2,
        extraction_method=ExtractionMethod.TEXT,
        extraction_confidence=1.0,
        raw_text="1. Explain overfitting. [10]",
        question_text="Explain overfitting.",
        source_line_start=4,
        source_line_end=4,
        dataset_version="v_deadbeef1234",
        origin=DataOrigin.FIXTURE,
        marks=AnnotationProvenance(value=10.0, source=LabelSource.RULE_INFERRED, confidence=1.0),
        bloom=AnnotationProvenance(value="Understand", source=LabelSource.LLM_PREDICTED, confidence=0.72),
        question_type=AnnotationProvenance(value=QuestionType.LONG_ANSWER, source=LabelSource.MODEL_PREDICTED),
    )
    dumped = q.model_dump()
    restored = Question.model_validate(dumped)

    assert restored.marks.value == 10.0
    assert restored.marks.source == LabelSource.RULE_INFERRED
    assert restored.bloom.value == "Understand"
    assert restored.bloom.is_reliable(min_confidence=0.7) is True
    assert restored.origin == DataOrigin.FIXTURE
    assert restored.source_line_start == 4


def test_low_confidence_prediction_is_not_reliable_until_teacher_verifies():
    provenance = AnnotationProvenance(value="Apply", source=LabelSource.LLM_PREDICTED, confidence=0.4)
    assert provenance.is_reliable() is False

    provenance.teacher_verified = True
    assert provenance.is_reliable() is True


def test_manually_entered_and_teacher_verified_are_distinct_sources():
    manual = AnnotationProvenance(value="Create", source=LabelSource.MANUALLY_ENTERED)
    verified = AnnotationProvenance(value="Create", source=LabelSource.LLM_PREDICTED, teacher_verified=True)
    assert manual.source != verified.source
    assert manual.is_reliable() is False  # no confidence, no verification flag set
    assert verified.is_reliable() is True
