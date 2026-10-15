"""Baseline paper generators for the comparison experiment (docs/EVALUATION_GENERATION.md).

  bank_copy  — pick questions straight from the historical bank (no generation, no LLM)
  llm_only   — one prompt asking the LLM for the whole paper as JSON; no retrieval, no solver, no checks
  rag_slots  — per-question LLM generation with retrieved exemplars, CO round-robin and level sampled
               from the target; ONE candidate per slot, no solver, no ranking, no critic
The full system adds: CP-SAT allocation, N candidates, filtering/ranking and the moderator critic.
"""

from __future__ import annotations

import numpy as np
from pydantic import ValidationError

from src.generation import prompts
from src.generation.blueprint import Blueprint
from src.generation.generator import Candidate, _exemplar_block, _exemplars
from src.generation.render import PaperQuestion
from src.generation.topics import HistoryProfile, marks_prior
from src.llm.ollama import LLMOutputError, LLMUnavailableError, OllamaClient
from src.optimization.allocator import _choice_positions


def _slots(bp: Blueprint):
    """(section, item, part, marks) for every question the blueprint asks for."""
    n = 0
    for s in bp.sections:
        ch = _choice_positions(s.n_items, s.n_choice)
        for i in range(s.n_items):
            n += 1
            if i in ch:
                yield s.label, n, "a", s.marks_each
                yield s.label, n, "b", s.marks_each
            else:
                yield s.label, n, None, s.marks_each


def bank_copy(bp: Blueprint, profile: HistoryProfile, rng: np.random.Generator) -> list[PaperQuestion]:
    qs = []
    cos = sorted(bp.outcomes)
    pool = profile.questions
    last_pick: dict[int, dict] = {}
    for sec, item, part, marks in _slots(bp):
        same = [q for q in pool if abs(q["marks"] - marks) < 1e-9] or pool
        q = same[int(rng.integers(len(same)))]
        co = q["course_outcomes"][0] if q["course_outcomes"] and q["course_outcomes"][0] in bp.outcomes else cos[int(rng.integers(len(cos)))]
        qs.append(PaperQuestion(sec, item, part, q["text"], marks, co, int(q["rbt"][0][1])))
    return qs


def llm_only(bp: Blueprint, client: OllamaClient) -> tuple[list[PaperQuestion], dict]:
    info = {"parse_ok": False}
    try:
        raw = client.chat_json(prompts.LLM_ONLY_SYSTEM, prompts.llm_only_user(bp), temperature=0.7, seed=bp.seed, max_tokens=4500)
    except (LLMOutputError, LLMUnavailableError) as exc:
        info["error"] = str(exc)
        return [], info
    out = []
    for r in raw.get("questions", []) if isinstance(raw, dict) else []:
        try:
            marks = float(r["marks"])
            co = str(r.get("co", "CO1")).upper().replace(" ", "")
            out.append(PaperQuestion(str(r["section"]).upper(), int(r["item"]), r.get("part") or None, str(r["text"]), marks,
                                     co, int(r.get("level", 2))))
        except (KeyError, ValueError, TypeError):
            continue
    info["parse_ok"] = bool(out)
    return out, info


def rag_slots(bp: Blueprint, profile: HistoryProfile, client: OllamaClient, rng: np.random.Generator) -> list[PaperQuestion]:
    cos = sorted(bp.outcomes)
    freq = np.array([c.freq for c in profile.clusters], dtype=float)
    out, k = [], 0
    last: dict[int, tuple[str, int]] = {}
    for sec, item, part, marks in _slots(bp):
        if part == "b" and item in last:
            co, level = last[item]
        else:
            co = cos[k % len(cos)]
            k += 1
            if bp.bloom_target:
                lv = np.array([bp.bloom_target.get(l, 0.0) for l in range(1, 7)])
            else:
                lv = marks_prior(profile, marks)
            level = int(rng.choice(range(1, 7), p=lv / lv.sum()))
            last[item] = (co, level)
        cl = int(rng.choice(len(profile.clusters), p=freq / freq.sum()))
        ex = _exemplars(profile, cl)
        user = prompts.generation_user(bp.course_name.title(), co, bp.outcomes[co], level, marks, profile.clusters[cl].keywords[:5],
                                       _exemplar_block(ex))
        try:
            cand = Candidate.model_validate(client.chat_json(prompts.GENERATION_SYSTEM, user, temperature=0.85,
                                                             seed=int(rng.integers(1, 10**6)), max_tokens=500))
            text = cand.question
        except (LLMOutputError, LLMUnavailableError, ValidationError):
            text = ""
        out.append(PaperQuestion(sec, item, part, text, marks, co, level))
    return out
