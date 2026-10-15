"""Novelty/duplicate scorer interface (master-prompt §28, Phase 0.5 §22).

§28 explicitly forbids a single cosine-similarity threshold — a real implementation must layer
exact-duplicate (hash), lexical near-duplicate, semantic-duplicate (embedding), and conceptual
repetition checks. The interface returns all four sub-scores rather than one collapsed number, so
that layering can't be silently lost by a future implementation.

Not implemented yet: needs a historical question corpus with embeddings to compare against, which
needs the dataset + extraction + embeddings pipeline (src/embeddings/, not yet built) to exist first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.utils.not_implemented import ComponentNotYetAvailableError


@dataclass
class NoveltyResult:
    is_exact_duplicate: bool
    lexical_similarity: float | None       # 0-1 against nearest historical question, None if not computed
    semantic_similarity: float | None      # 0-1 embedding cosine sim against nearest historical question
    conceptual_repetition: bool | None     # same concept + same cognitive framing as a prior question
    nearest_historical_question_id: str | None


class NoveltyScorer(ABC):
    @abstractmethod
    def score(self, question_text: str) -> NoveltyResult:
        """Score a candidate question's novelty against the historical corpus. Must populate every
        sub-score it is capable of computing — never collapse to a single number."""


class NotYetAvailableNoveltyScorer(NoveltyScorer):
    def score(self, question_text: str) -> NoveltyResult:
        raise ComponentNotYetAvailableError(
            "NoveltyScorer",
            "no historical question corpus/embedding index exists yet to compare against.",
        )
