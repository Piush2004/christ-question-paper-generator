"""Deterministic constraint allocator: decides, for every question slot, the course outcome, RBT level
and historical topic cluster — BEFORE any language model is called.

Why a solver and not an LLM: a prompt like "30% Understand, 40% Apply" can silently drift; a CP-SAT
model either satisfies the hard constraints or proves it cannot. Hard vs soft:

  HARD (never violated; infeasibility is reported with reasons):
    * every course outcome is examined at least once
    * a level with a 0 target is never used
    * no topic cluster takes more than its fair cap of slots (anti-repetition)
    * OR-alternatives share CO and level and differ in topic

  SOFT, measured and reported (marks are indivisible, so exact shares are not always attainable):
    * marks-weighted RBT share vs the teacher's target (or the course's historical marks→level prior)
    * marks-weighted CO share vs target (default: the course's historical CO mix)
    * topic preference: blend of historical frequency and under-asked topics (`history_weight`),
      penalty for topics already used in the most recent paper, penalty for CO/topic pairs never
      seen together historically.

Solver is single-threaded with a fixed seed => the same blueprint + history gives the same allocation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from ortools.sat.python import cp_model

from src.generation.blueprint import Blueprint
from src.generation.topics import HistoryProfile, marks_prior

SCALE = 100  # fixed-point scale for marks / shares


@dataclass
class Slot:
    section: str
    item: int                      # global question number (1-based)
    part: str | None               # None, "a" or "b" for OR alternatives
    marks: float
    co: str
    level: int
    cluster: int


@dataclass
class Allocation:
    slots: list[Slot]
    report: dict
    problems: list[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return not self.problems


class InfeasibleBlueprint(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _choice_positions(n_items: int, n_choice: int) -> set[int]:
    if n_choice <= 0:
        return set()
    return {min(n_items - 1, int((k + 0.5) * n_items / n_choice)) for k in range(n_choice)}


def precheck(bp: Blueprint, profile: HistoryProfile) -> list[str]:
    problems = bp.validate()
    n_items = sum(s.n_items for s in bp.sections)
    if bp.bloom_target is not None:
        positive = [l for l, v in bp.bloom_target.items() if v > 0]
        if len(positive) > n_items:
            problems.append(f"{len(positive)} different RBT levels requested but the paper has only {n_items} items.")
        min_marks = min(s.marks_each for s in bp.sections)
        for l in positive:
            if bp.bloom_target[l] * bp.max_marks < min_marks / 2:
                problems.append(f"Level L{l} target ({bp.bloom_target[l]:.0%} = {bp.bloom_target[l]*bp.max_marks:.1f} marks) is "
                                f"smaller than half the smallest question ({min_marks:g} marks) — it cannot be represented. "
                                f"Raise it to at least {min_marks / 2 / bp.max_marks:.0%} or set it to 0.")
    if len(profile.clusters) == 0:
        problems.append("No historical topic structure for this course — upload previous papers first.")
    return problems


def allocate(bp: Blueprint, profile: HistoryProfile, time_limit_s: float = 20.0) -> Allocation:
    problems = precheck(bp, profile)
    if problems:
        raise InfeasibleBlueprint(problems)

    # ---------------------------------------------------------------- items & slots
    items: list[dict] = []          # one per numbered item
    num = 0
    for s in bp.sections:
        choice_pos = _choice_positions(s.n_items, s.n_choice)
        for i in range(s.n_items):
            num += 1
            items.append({"no": num, "section": s.label, "marks": s.marks_each, "choice": i in choice_pos})
    n = len(items)
    cos = sorted(bp.outcomes)
    n_co, n_cl = len(cos), len(profile.clusters)
    levels = list(range(1, 7))
    M = float(bp.max_marks)

    m = cp_model.CpModel()
    lvl = {(i, l): m.NewBoolVar(f"l{i}_{l}") for i in range(n) for l in levels}
    co = {(i, c): m.NewBoolVar(f"c{i}_{c}") for i in range(n) for c in range(n_co)}
    cl = {(i, t): m.NewBoolVar(f"t{i}_{t}") for i in range(n) for t in range(n_cl)}
    alt_idx = [i for i, it in enumerate(items) if it["choice"]]
    cl2 = {(i, t): m.NewBoolVar(f"t2{i}_{t}") for i in alt_idx for t in range(n_cl)}
    for i in range(n):
        m.AddExactlyOne(lvl[i, l] for l in levels)
        m.AddExactlyOne(co[i, c] for c in range(n_co))
        m.AddExactlyOne(cl[i, t] for t in range(n_cl))
    for i in alt_idx:
        m.AddExactlyOne(cl2[i, t] for t in range(n_cl))
        for t in range(n_cl):
            m.Add(cl[i, t] + cl2[i, t] <= 1)          # alternatives cover different topics

    # --- HARD: every CO examined at least once
    for c in range(n_co):
        m.Add(sum(co[i, c] for i in range(n)) >= 1)
    # --- HARD: topic cap (anti-repetition) over all question slots
    n_slots = n + len(alt_idx)
    cap = math.ceil(n_slots / n_cl) + 1
    for t in range(n_cl):
        m.Add(sum(cl[i, t] for i in range(n)) + sum(cl2[i, t] for i in alt_idx) <= cap)
    # --- HARD: zero-target levels unused
    if bp.bloom_target is not None:
        for l in levels:
            if bp.bloom_target.get(l, 0.0) <= 0.0:
                for i in range(n):
                    m.Add(lvl[i, l] == 0)

    obj_terms = []

    # --- SOFT: Bloom
    if bp.bloom_target is not None:
        for l in levels:
            got = sum(int(items[i]["marks"] * SCALE) * lvl[i, l] for i in range(n))
            want = int(round(bp.bloom_target.get(l, 0.0) * M * SCALE))
            d = m.NewIntVar(0, int(M * SCALE), f"bd{l}")
            m.Add(d >= got - want)
            m.Add(d >= want - got)
            obj_terms.append(4 * d)
    else:
        for s in bp.sections:
            idxs = [i for i, it in enumerate(items) if it["section"] == s.label]
            prior = marks_prior(profile, s.marks_each)
            for l in levels:
                want = int(round(prior[l - 1] * len(idxs) * SCALE))
                got = sum(SCALE * lvl[i, l] for i in idxs)
                d = m.NewIntVar(0, len(idxs) * SCALE, f"pd{s.label}{l}")
                m.Add(d >= got - want)
                m.Add(d >= want - got)
                obj_terms.append(2 * d)

    # --- SOFT: CO share
    weights = bp.co_weights or {c: profile.co_share.get(c, 0.0) for c in cos}
    wsum = sum(weights.get(c, 0.0) for c in cos)
    shares = {c: (weights.get(c, 0.0) / wsum if wsum > 0 else 1.0 / n_co) for c in cos}
    for ci, c in enumerate(cos):
        got = sum(int(items[i]["marks"] * SCALE) * co[i, ci] for i in range(n))
        want = int(round(shares[c] * M * SCALE))
        d = m.NewIntVar(0, int(M * SCALE), f"cd{ci}")
        m.Add(d >= got - want)
        m.Add(d >= want - got)
        obj_terms.append(2 * d)

    # --- SOFT: topic preference
    freq = np.array([c.freq for c in profile.clusters], dtype=float)
    fn = freq / freq.max()
    hw = bp.history_weight
    pref = hw * fn + (1 - hw) * (1 - fn)              # 0..1 desirability
    for t in range(n_cl):
        recent_pen = 0.35 if t in profile.recent_cluster_ids else 0.0
        val = int(round((pref[t] - recent_pen) * 60))
        for i in range(n):
            obj_terms.append(-val * cl[i, t])
        for i in alt_idx:
            obj_terms.append(-val * cl2[i, t])
    # CO/topic pairs never seen together historically are discouraged (not forbidden)
    for ci, c in enumerate(cos):
        for t in range(n_cl):
            if profile.clusters[t].co_counts.get(c, 0) == 0:
                for i in range(n):
                    z = m.NewBoolVar(f"z{i}_{ci}_{t}")
                    m.AddBoolAnd([co[i, ci], cl[i, t]]).OnlyEnforceIf(z)
                    m.AddBoolOr([co[i, ci].Not(), cl[i, t].Not(), z])
                    obj_terms.append(25 * z)

    # --- alternatives share CO and level with their primary (structural, via one slot per item) ---
    m.Minimize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = bp.seed
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise InfeasibleBlueprint(_explain(bp, profile, n, n_co, n_cl, cap))

    slots: list[Slot] = []
    for i, it in enumerate(items):
        L = next(l for l in levels if solver.Value(lvl[i, l]))
        C = cos[next(c for c in range(n_co) if solver.Value(co[i, c]))]
        T = next(t for t in range(n_cl) if solver.Value(cl[i, t]))
        if it["choice"]:
            T2 = next(t for t in range(n_cl) if solver.Value(cl2[i, t]))
            slots.append(Slot(it["section"], it["no"], "a", it["marks"], C, L, T))
            slots.append(Slot(it["section"], it["no"], "b", it["marks"], C, L, T2))
        else:
            slots.append(Slot(it["section"], it["no"], None, it["marks"], C, L, T))

    return Allocation(slots, allocation_report(bp, profile, slots, shares, status == cp_model.OPTIMAL))


def allocation_report(bp: Blueprint, profile: HistoryProfile, slots: list[Slot], co_shares: dict[str, float],
                      optimal: bool) -> dict:
    M = float(bp.max_marks)
    per_item: dict[int, Slot] = {}
    for s in slots:
        per_item.setdefault(s.item, s)
    bloom_marks = {l: sum(s.marks for s in per_item.values() if s.level == l) for l in range(1, 7)}
    co_marks = {c: sum(s.marks for s in per_item.values() if s.co == c) for c in bp.outcomes}
    tol = max(2.0, 0.05 * M)
    rep = {
        "solver_status": "optimal" if optimal else "feasible (time-limited)",
        "bloom_marks_share": {f"L{l}": round(v / M, 3) for l, v in bloom_marks.items()},
        "co_marks_share": {c: round(v / M, 3) for c, v in co_marks.items()},
        "co_target_share": {c: round(v, 3) for c, v in co_shares.items()},
        "all_cos_covered": all(v > 0 for v in co_marks.values()),
        "topic_usage": {profile.clusters[t].label: sum(1 for s in slots if s.cluster == t) for t in range(len(profile.clusters))},
    }
    if bp.bloom_target is not None:
        dev = {f"L{l}": round(bloom_marks[l] - bp.bloom_target.get(l, 0.0) * M, 2) for l in range(1, 7)}
        rep["bloom_target_share"] = {f"L{l}": v for l, v in bp.bloom_target.items()}
        rep["bloom_deviation_marks"] = dev
        rep["bloom_within_tolerance"] = all(abs(v) <= tol for v in dev.values())
        rep["bloom_tolerance_marks"] = tol
    return rep


def _explain(bp, profile, n, n_co, n_cl, cap) -> list[str]:
    out = [f"The constraints cannot all be met together (solver proved infeasibility)."]
    if n < n_co:
        out.append(f"Only {n} questions for {n_co} course outcomes — every outcome must appear at least once.")
    if cap * n_cl < n:
        out.append(f"Topic-spread cap ({cap} per topic × {n_cl} topics) is below the {n} questions needed; "
                   "upload more historical papers so more topics are known, or reduce questions.")
    if bp.bloom_target is not None:
        zero = [f"L{l}" for l in range(1, 7) if bp.bloom_target.get(l, 0) <= 0]
        out.append(f"Levels {', '.join(zero)} are forbidden by the Bloom target; relax them or allow some marks at those levels.")
    return out
