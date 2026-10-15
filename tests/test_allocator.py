"""Constraint allocator tests on a synthetic (fixture) history profile — no model/encoder needed."""
from collections import Counter

import numpy as np
import pytest

from src.generation.blueprint import Blueprint, SectionSpec
from src.generation.topics import HistoryProfile, TopicCluster
from src.optimization.allocator import InfeasibleBlueprint, allocate


def make_profile(n_clusters=6, cos=("CO1", "CO2", "CO3")) -> HistoryProfile:
    clusters = [TopicCluster(i, f"topic{i}", [f"kw{i}"], [], np.eye(n_clusters)[i], freq=5 + i,
                             co_counts={c: 1 for c in cos}) for i in range(n_clusters)]
    prior = {m: np.array([.2, .25, .25, .15, .1, .05]) for m in (2.0, 5.0, 10.0)}
    return HistoryProfile("x", [], np.zeros((0, n_clusters)), clusters, {c: 1 / len(cos) for c in cos}, prior, set(), [])


def make_bp(**kw) -> Blueprint:
    base = dict(course_code="T101", course_name="TEST", semester=1, exam_session="November 2025", max_marks=100,
                duration_minutes=180, outcomes={"CO1": "a", "CO2": "b", "CO3": "c"},
                sections=[SectionSpec("A", 10, 2), SectionSpec("B", 6, 5, 2), SectionSpec("C", 5, 10, 1)])
    base.update(kw)
    return Blueprint(**base)


def test_counts_marks_and_coverage():
    bp = make_bp()
    a = allocate(bp, make_profile())
    assert len({s.item for s in a.slots}) == 21
    assert len(a.slots) == bp.n_questions == 24             # + 3 OR alternatives
    assert {s.co for s in a.slots} == {"CO1", "CO2", "CO3"}  # hard: every CO examined
    assert a.report["all_cos_covered"]


def test_or_alternatives_share_co_level_and_differ_in_topic():
    a = allocate(make_bp(), make_profile())
    by_item: dict[int, list] = {}
    for s in a.slots:
        by_item.setdefault(s.item, []).append(s)
    pairs = [v for v in by_item.values() if len(v) == 2]
    assert len(pairs) == 3
    for x, y in pairs:
        assert (x.co, x.level, x.marks) == (y.co, y.level, y.marks) and x.cluster != y.cluster


def test_explicit_bloom_target_is_met_within_tolerance_and_zero_levels_unused():
    a = allocate(make_bp(bloom_target={2: 0.3, 3: 0.4, 4: 0.3}), make_profile())
    assert a.report["bloom_within_tolerance"]
    assert {s.level for s in a.slots} <= {2, 3, 4}


def test_deterministic_for_same_seed():
    a1 = allocate(make_bp(), make_profile())
    a2 = allocate(make_bp(), make_profile())
    key = lambda a: [(s.item, s.part, s.co, s.level, s.cluster) for s in a.slots]  # noqa: E731
    assert key(a1) == key(a2)


def test_topic_cap_prevents_repetition():
    a = allocate(make_bp(), make_profile(n_clusters=6))
    cap = -(-len(a.slots) // 6) + 1
    assert max(Counter(s.cluster for s in a.slots).values()) <= cap


@pytest.mark.parametrize("kw,fragment", [
    (dict(max_marks=90), "add up to"),
    (dict(bloom_target={2: 0.5, 3: 0.4}), "add up to"),
    (dict(bloom_target={1: 0.001, 2: 0.5, 3: 0.499}), "cannot be represented"),
    (dict(outcomes={f"CO{i}": "x" for i in range(1, 30)}), "cannot cover all"),
    (dict(sections=[SectionSpec("A", 10, 2), SectionSpec("B", 6, 5, 9), SectionSpec("C", 5, 10)]), "choice"),
])
def test_impossible_or_contradictory_blueprints_are_rejected_with_reasons(kw, fragment):
    with pytest.raises(InfeasibleBlueprint) as e:
        allocate(make_bp(**kw), make_profile())
    assert any(fragment in p for p in e.value.problems)
