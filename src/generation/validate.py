"""Deterministic paper validation — run on every generated paper before it can be approved/exported.
No model is involved here; each check is arithmetic or string logic against the blueprint.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.embeddings.encoder import encode
from src.generation.blueprint import Blueprint
from src.generation.generator import _FIGURE_REF, jaccard_3gram, word_range
from src.generation.render import PaperQuestion


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    hard: bool = True


def validate_paper(bp: Blueprint, qs: list[PaperQuestion], history_texts: list[str] | None = None,
                   history_emb: np.ndarray | None = None, dup_sim: float = 0.88) -> list[Check]:
    checks: list[Check] = []
    by_sec: dict[str, dict[int, list[PaperQuestion]]] = {}
    for q in qs:
        by_sec.setdefault(q.section, {}).setdefault(q.item, []).append(q)

    # structure
    ok_items = all(len(by_sec.get(s.label, {})) == s.n_items for s in bp.sections)
    checks.append(Check("items_per_section", ok_items,
                        ", ".join(f"{s.label}: {len(by_sec.get(s.label, {}))}/{s.n_items}" for s in bp.sections)))
    choice_ok = all(sum(1 for it in by_sec.get(s.label, {}).values() if len(it) == 2) == s.n_choice for s in bp.sections) \
        and all(len(it) <= 2 for sec in by_sec.values() for it in sec.values())
    checks.append(Check("choice_items", choice_ok, "OR-alternative count per section matches the blueprint"))
    marks_ok = all(abs(q.marks - next(s.marks_each for s in bp.sections if s.label == q.section)) < 1e-9 for q in qs)
    checks.append(Check("marks_per_question", marks_ok, "every question carries its section's marks"))
    total = sum(max(q.marks for q in it) for sec in by_sec.values() for it in sec.values())
    checks.append(Check("total_marks", abs(total - bp.max_marks) < 1e-9, f"{total:g} / {bp.max_marks}"))
    alt_ok = all(len({(x.co, x.level) for x in it}) == 1 for sec in by_sec.values() for it in sec.values())
    checks.append(Check("alternatives_same_outcome_level", alt_ok, "OR alternatives test the same CO and RBT level"))

    # curriculum + cognition
    cos = {q.co for q in qs}
    missing = sorted(set(bp.outcomes) - cos)
    checks.append(Check("all_course_outcomes_covered", not missing, f"missing: {missing}" if missing else f"{len(cos)}/{len(bp.outcomes)} covered"))
    checks.append(Check("valid_levels", all(1 <= q.level <= 6 for q in qs), "all RBT levels in L1..L6"))
    if bp.bloom_target:
        per_item = {(q.section, q.item): q for q in qs}
        share = {l: sum(q.marks for q in per_item.values() if q.level == l) / bp.max_marks for l in range(1, 7)}
        tol = max(2.0, 0.05 * bp.max_marks) / bp.max_marks
        dev = {l: share[l] - bp.bloom_target.get(l, 0.0) for l in range(1, 7)}
        checks.append(Check("bloom_target", all(abs(v) <= tol for v in dev.values()),
                            "deviation (share): " + ", ".join(f"L{l} {v:+.2f}" for l, v in dev.items() if abs(v) > 1e-9) or "exact",
                            hard=False))

    # text quality
    short = [f"Q{q.item}{q.part or ''}" for q in qs if len(q.text.split()) < word_range(q.marks)[0]]
    checks.append(Check("question_length", not short, f"too short: {short}" if short else "all within range for their marks"))
    figs = [f"Q{q.item}{q.part or ''}" for q in qs if _FIGURE_REF.search(q.text)]
    checks.append(Check("self_contained", not figs, f"refer to missing figure/table: {figs}" if figs else "no dangling figure references"))
    empties = [q.item for q in qs if not q.text.strip()]
    checks.append(Check("non_empty", not empties, f"empty: {empties}" if empties else "ok"))

    # duplicates
    if len(qs) > 1:
        e = encode([q.text for q in qs])
        s = e @ e.T
        np.fill_diagonal(s, 0)
        pairs = [(qs[i], qs[j]) for i in range(len(qs)) for j in range(i + 1, len(qs)) if s[i, j] > dup_sim
                 and not (qs[i].item == qs[j].item)]
        checks.append(Check("no_duplicates_within_paper", not pairs,
                            ", ".join(f"Q{a.item}~Q{b.item}" for a, b in pairs) if pairs else f"max pairwise similarity {float(s.max()):.2f}"))
    if history_emb is not None and len(history_emb):
        e = encode([q.text for q in qs])
        sims = e @ history_emb.T
        worst = sims.max(axis=1)
        copies = [f"Q{qs[i].item}{qs[i].part or ''}" for i in range(len(qs))
                  if worst[i] > dup_sim or (history_texts and jaccard_3gram(qs[i].text, history_texts[int(sims[i].argmax())]) > 0.6)]
        checks.append(Check("not_copied_from_history", not copies,
                            f"too similar to a past question: {copies}" if copies else f"max similarity to history {float(worst.max()):.2f}"))
    return checks


def summarize(checks: list[Check]) -> dict:
    hard_fail = [c.name for c in checks if c.hard and not c.passed]
    soft_fail = [c.name for c in checks if not c.hard and not c.passed]
    return {"approvable": not hard_fail, "hard_failures": hard_fail, "soft_warnings": soft_fail,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail, "hard": c.hard} for c in checks]}
