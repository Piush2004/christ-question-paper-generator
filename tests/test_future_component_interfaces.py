"""Proves every not-yet-implemented ML component interface fails loudly rather than fabricating a
value (master-prompt Rule 66, Phase 0.5 §22)."""

import pytest

from src.bloom.interface import NotYetAvailableBloomClassifier
from src.difficulty.interface import NotYetAvailableDifficultyEstimator
from src.dok.interface import NotYetAvailableDOKClassifier
from src.generation.interface import BlueprintSlot, NotYetAvailableQuestionGenerator
from src.novelty.interface import NotYetAvailableNoveltyScorer
from src.optimization.interface import NotYetAvailablePaperOptimizer
from src.utils.not_implemented import ComponentNotYetAvailableError


def test_bloom_classifier_raises_not_fabricates():
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailableBloomClassifier().predict("Explain overfitting.")


def test_dok_classifier_raises_not_fabricates():
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailableDOKClassifier().predict("Explain overfitting.")


def test_difficulty_estimator_raises_not_fabricates():
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailableDifficultyEstimator().predict("Explain overfitting.", marks=10)


def test_question_generator_raises_not_fabricates():
    slot = BlueprintSlot(unit="Unit 1", topic="Overfitting", marks=10, bloom_level="Analyze", dok_level=3,
                          difficulty_target="hard")
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailableQuestionGenerator().generate(slot)


def test_novelty_scorer_raises_not_fabricates():
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailableNoveltyScorer().score("Explain overfitting.")


def test_paper_optimizer_raises_not_fabricates():
    with pytest.raises(ComponentNotYetAvailableError):
        NotYetAvailablePaperOptimizer().optimize(["q1", "q2"])


def test_error_message_points_to_research_gap_doc():
    with pytest.raises(ComponentNotYetAvailableError, match="docs/RESEARCH_GAP.md"):
        NotYetAvailableBloomClassifier().predict("x")
