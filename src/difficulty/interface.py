"""Difficulty estimator interface (master-prompt §24/§25, Phase 0.5 §22).

Per §25, without real student-response data any output here is an ESTIMATE, never a psychometrically
calibrated difficulty — the interface's return type/docstring encodes that distinction so no caller
can accidentally treat `predict()`'s output as IRT-calibrated (see src/psychometrics/, not yet built,
for the explicitly-labelled `simulated` psychometric layer instead).

Not implemented yet: no structural-feature training/eval data (concept counts, expert difficulty
labels) exists until annotation runs on a real dataset.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.question import AnnotationProvenance
from src.utils.not_implemented import ComponentNotYetAvailableError


class DifficultyEstimator(ABC):
    """Estimates a question's difficulty. NOT psychometrically calibrated (§25) — always an
    estimate derived from structural features / expert labels / LLM judgment."""

    @abstractmethod
    def predict(self, question_text: str, marks: float | None = None) -> AnnotationProvenance[float]:
        """Return an AnnotationProvenance wrapping a difficulty score (implementation defines the
        scale, e.g. 0-1), with `source` set appropriately and a genuine confidence — never a
        placeholder."""


class NotYetAvailableDifficultyEstimator(DifficultyEstimator):
    def predict(self, question_text: str, marks: float | None = None) -> AnnotationProvenance[float]:
        raise ComponentNotYetAvailableError(
            "DifficultyEstimator",
            "no structural-feature training/eval data or expert difficulty labels exist yet.",
        )
