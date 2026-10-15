"""Bloom's taxonomy classifier interface (master-prompt §22, Phase 0.5 §22).

Not implemented yet: §22 requires comparing at least two approaches (embedding+classifier vs.
fine-tuned encoder vs. LLM classifier) with REAL measured accuracy/F1 before any one is selected —
that comparison needs a gold-labelled dataset that doesn't exist until annotation (§14) runs, which
itself needs a real historical-paper dataset that hasn't arrived (see docs/RESEARCH_GAP.md sequencing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.question import AnnotationProvenance
from src.utils.not_implemented import ComponentNotYetAvailableError

BLOOM_LEVELS = ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create")


class BloomClassifier(ABC):
    """Predicts a Bloom's taxonomy level for a single question's text."""

    @abstractmethod
    def predict(self, question_text: str) -> AnnotationProvenance[str]:
        """Return an AnnotationProvenance wrapping one of BLOOM_LEVELS, with `source` set to
        MODEL_PREDICTED or LLM_PREDICTED and a genuine confidence score — never a placeholder."""


class NotYetAvailableBloomClassifier(BloomClassifier):
    def predict(self, question_text: str) -> AnnotationProvenance[str]:
        raise ComponentNotYetAvailableError(
            "BloomClassifier",
            "no gold-labelled Bloom dataset exists yet to train or evaluate a classifier against.",
        )
