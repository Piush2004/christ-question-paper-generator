"""Webb's Depth-of-Knowledge classifier interface (master-prompt §23, Phase 0.5 §22).

Kept structurally independent from src/bloom/ — §23 explicitly forbids conflating Bloom and DOK;
they are separate constructs and must be evaluated separately even though both classify a question's
cognitive demand.

Not implemented yet: same blocker as BloomClassifier — no gold-labelled DOK dataset exists.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.question import AnnotationProvenance
from src.utils.not_implemented import ComponentNotYetAvailableError

DOK_LEVELS = (1, 2, 3, 4)  # Recall, Skill/Concept, Strategic Thinking, Extended Thinking


class DOKClassifier(ABC):
    """Predicts a Webb DOK level (1-4) for a single question's text."""

    @abstractmethod
    def predict(self, question_text: str) -> AnnotationProvenance[int]:
        """Return an AnnotationProvenance wrapping one of DOK_LEVELS, with `source` set to
        MODEL_PREDICTED or LLM_PREDICTED and a genuine confidence score — never a placeholder."""


class NotYetAvailableDOKClassifier(DOKClassifier):
    def predict(self, question_text: str) -> AnnotationProvenance[int]:
        raise ComponentNotYetAvailableError(
            "DOKClassifier",
            "no gold-labelled DOK dataset exists yet to train or evaluate a classifier against.",
        )
