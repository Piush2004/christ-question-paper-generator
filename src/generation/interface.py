"""Question generator interface (master-prompt §32/§35/§36, Phase 0.5 §22).

Provider-agnostic by design (§35: "the research system should be able to compare different
generators") — LocalLLM / APIModel / FineTunedModel implementations all satisfy this same interface,
so the blueprint→candidate-generation stage never hard-codes a specific provider.

Not implemented yet: needs a compiled assessment blueprint (src/blueprint/, not yet built) and a
curriculum/RAG context source (src/curriculum/, src/retrieval/, not yet built) to generate anything
grounded — building a generator with no real context source to draw from would just be prompting a
raw LLM with no way to validate output against a syllabus, which is exactly the gap this project
exists to close (docs/RESEARCH_GAP.md, Gap 1/2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.utils.not_implemented import ComponentNotYetAvailableError


@dataclass
class BlueprintSlot:
    """One cell of a compiled assessment blueprint (§30) — the unit of work a generator fills.
    Minimal by design; extended once src/blueprint/ defines the full blueprint compiler."""

    unit: str
    topic: str
    marks: float
    bloom_level: str
    dok_level: int
    difficulty_target: str


@dataclass
class GeneratedCandidate:
    """Structured LLM output for one generated question (§36 schema)."""

    question_text: str
    rationale: str
    source_context_ids: list[str]
    model_name: str
    prompt_version: str


class QuestionGenerator(ABC):
    """Generates candidate questions for a single blueprint slot. Implementations wrap a specific
    provider (LocalLLM / APIModel / FineTunedModel) behind this one interface."""

    @abstractmethod
    def generate(self, slot: BlueprintSlot, n_candidates: int = 5) -> list[GeneratedCandidate]:
        """Return `n_candidates` distinct candidates for the given slot. Must never return fewer
        than requested by silently padding with duplicates or fabricated text — raise instead."""


class NotYetAvailableQuestionGenerator(QuestionGenerator):
    def generate(self, slot: BlueprintSlot, n_candidates: int = 5) -> list[GeneratedCandidate]:
        raise ComponentNotYetAvailableError(
            "QuestionGenerator",
            "no compiled blueprint or curriculum/RAG context source exists yet to ground generation.",
        )
