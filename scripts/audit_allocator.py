"""Allocator robustness audit on randomly shaped blueprints.

Generates blueprints of varied shape (2-4 sections, 3-12 items, mixed marks, OR-items, explicit Bloom targets),
a fraction with INJECTED contradictions (marks total mismatch, un-representable tiny Bloom share, more OR-items
than items). For each: run the allocator, then verify the result with an INDEPENDENT checker that does not
reuse allocator code. Reports: solved & verified, solved with Bloom deviation > tolerance (reported, not hidden),
rejected-with-reasons, and — the important ones — false rejections (a sound blueprint that was refused) and
unsound solutions (a returned allocation that violates a hard constraint). Both must be zero."""

from __future__ import annotations

import json
import random
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from src.generation.blueprint import Blueprint, SectionSpec, load_papers, load_questions  # noqa: E402
from src.generation.pipeline import history_for  # noqa: E402
from src.optimization.allocator import InfeasibleBlueprint, allocate  # noqa: E402


def make(rng: random.Random, outcomes: dict, inject: str | None) -> Blueprint:
    secs = []
    for k in range(rng.randint(2, 4)):
        n = rng.randint(3, 10)
        secs.append(SectionSpec("ABCD"[k], n, float(rng.choice([2, 3, 5, 6, 8, 10])), rng.randint(0, n // 2)))
    total = int(sum(s.total_marks for s in secs))
    levels = rng.sample(range(1, 7), rng.randint(2, 4))
    w = [rng.random() + 0.3 for _ in levels]
    target = {l: round(x / sum(w), 2) for l, x in zip(levels, w)}
    drift = round(1.0 - sum(target.values()), 2)
    target[levels[0]] = round(target[levels[0]] + drift, 2)
    if rng.random() < 0.5:
        target = None
    bp = Blueprint(course_code="X1", course_name="X", semester=1, exam_session="November 2025", max_marks=total, duration_minutes=180,
                   outcomes=outcomes, sections=secs, bloom_target=target, seed=rng.randint(1, 999))
    if inject == "marks_mismatch":
        bp.max_marks = total + rng.choice([5, 10, -10])
    elif inject == "tiny_share":
        bp.bloom_target = {1: 0.001, 2: 0.5, 3: 0.499}
    elif inject == "too_many_choice":
        secs[0].n_choice = secs[0].n_items + 2
    return bp


def verify(bp: Blueprint, alloc, n_clusters: int) -> list[str]:
    """Independent hard-constraint check of a returned allocation."""
    bad = []
    slots = alloc.slots
    items = {}
    for s in slots:
        items.setdefault(s.item, []).append(s)
    if len(items) != sum(x.n_items for x in bp.sections):
        bad.append("item_count")
    if len(slots) != bp.n_questions:
        bad.append("question_count")
    sec_marks = {x.label: x.marks_each for x in bp.sections}
    if any(abs(s.marks - sec_marks[s.section]) > 1e-9 for s in slots):
        bad.append("marks_per_question")
    if sum(it[0].marks for it in items.values()) != bp.max_marks:
        bad.append("total_marks")
    if set(bp.outcomes) - {s.co for s in slots}:
        bad.append("co_not_covered")
    if bp.bloom_target:
        forb = {l for l in range(1, 7) if bp.bloom_target.get(l, 0.0) <= 0}
        if any(s.level in forb for s in slots):
            bad.append("forbidden_level_used")
    for it in items.values():
        if len(it) == 2 and (it[0].co != it[1].co or it[0].level != it[1].level or it[0].cluster == it[1].cluster):
            bad.append("alt_pair_rule")
    cap = -(-len(slots) // n_clusters) + 1
    if max(Counter(s.cluster for s in slots).values()) > cap:
        bad.append("topic_cap")
    return bad


def main(n: int = 48) -> None:
    papers, questions = load_papers(), load_questions()
    prof = history_for("graph_theory", papers, questions)
    outcomes = {"CO1": "a", "CO2": "b", "CO3": "c", "CO4": "d"}
    rng = random.Random(2026)
    rows = []
    for i in range(n):
        inject = rng.choice([None, None, None, "marks_mismatch", "tiny_share", "too_many_choice"])
        bp = make(rng, outcomes, inject)
        t0 = time.time()
        try:
            a = allocate(bp, prof, time_limit_s=4.0)
            bad = verify(bp, a, len(prof.clusters))
            dev_ok = a.report.get("bloom_within_tolerance", True)
            outcome = "unsound" if bad else ("solved_verified" if dev_ok else "solved_bloom_outside_tolerance")
            rows.append({"i": i, "inject": inject, "outcome": outcome, "violations": bad, "s": round(time.time() - t0, 1)})
        except InfeasibleBlueprint as e:
            rows.append({"i": i, "inject": inject, "outcome": "rejected", "reasons": e.problems, "s": round(time.time() - t0, 1)})
    c = Counter((r["outcome"], r["inject"] is not None) for r in rows)
    summary = {
        "n_blueprints": n, "sound_blueprints": sum(r["inject"] is None for r in rows), "injected_contradictions": sum(r["inject"] is not None for r in rows),
        "solved_verified": sum(r["outcome"] == "solved_verified" for r in rows),
        "solved_bloom_outside_tolerance": sum(r["outcome"] == "solved_bloom_outside_tolerance" for r in rows),
        "unsound_solutions(MUST BE 0)": sum(r["outcome"] == "unsound" for r in rows),
        "false_rejections(sound blueprint refused)": sum(r["outcome"] == "rejected" and r["inject"] is None for r in rows),
        "injected_and_rejected": sum(r["outcome"] == "rejected" and r["inject"] is not None for r in rows),
        "injected_but_accepted(MUST BE 0)": sum(r["outcome"] != "rejected" and r["inject"] is not None for r in rows),
        "median_solve_s": sorted(r["s"] for r in rows)[len(rows) // 2], "max_solve_s": max(r["s"] for r in rows),
    }
    d = ROOT / "results" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "allocator.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))
    for r in rows:
        if r["outcome"] in ("unsound", "solved_bloom_outside_tolerance") or (r["outcome"] == "rejected" and r["inject"] is None):
            print("  NOTE", r)


if __name__ == "__main__":
    main()
