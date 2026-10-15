"""Constraint-first paper generator.

Stages (all logged per question for provenance):
  1. allocation (src/optimization/allocator.py) fixed the CO / RBT level / topic cluster / marks of every slot
  2. N candidate questions per slot from the LLM, JSON-schema validated (malformed output is discarded)
  3. hard filters: novelty vs history, within-paper duplicates, self-containedness, length for marks
  4. ranking: trained Bloom classifier + verb check + topic/CO fit + novelty + length fit
  5. moderator critic (LLM) on the winner: answerability / ambiguity / missing data; fall through to the
     next-best candidate if rejected
Nothing in the paper is finalised here — the result is a draft for teacher review.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.bloom.lexicon import verb_level
from src.embeddings.encoder import encode
from src.generation import prompts
from src.generation.blueprint import Blueprint
from src.generation.render import PaperQuestion
from src.generation.topics import HistoryProfile
from src.llm.ollama import LLMOutputError, LLMUnavailableError, OllamaClient, wrap_untrusted
from src.optimization.allocator import Allocation, Slot


class LevelClassifier(Protocol):
    def predict_proba(self, texts: list[str], marks: list[float]) -> np.ndarray: ...


class Candidate(BaseModel):
    question: str = Field(min_length=8)
    topic: str = ""
    bloom_level: int = Field(ge=1, le=6)

    @field_validator("question")
    @classmethod
    def _clean(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v).strip()


class _DanglingReference:
    """Detects questions that point at material which is not in the question text: figures/tables/'given
    below', 'the following <data>', or a question that ends with a colon (the data never follows)."""
    _PAT = re.compile(r"\b(given (below|above)|following [a-z\- ]{0,30}?(graph|figure|diagram|table|matrix|network|tree|circuit|data|values|"
                      r"information|dataset)|shown (below|above)|figure \d|fig\.|refer (to )?the (figure|diagram|table))\b", re.IGNORECASE)

    def search(self, text: str):
        return self._PAT.search(text) or re.search(r":\s*$", text.strip())


_FIGURE_REF = _DanglingReference()
_WORD_RANGE = {3: (5, 45), 6: (7, 90), 99: (10, 170)}


def word_range(marks: float) -> tuple[int, int]:
    for lim, rng in _WORD_RANGE.items():
        if marks <= lim:
            return rng
    return _WORD_RANGE[99]


def jaccard_3gram(a: str, b: str) -> float:
    def grams(t: str) -> set[str]:
        w = re.findall(r"[a-z0-9]+", t.lower())
        return {" ".join(w[i:i + 3]) for i in range(max(1, len(w) - 2))}
    A, B = grams(a), grams(b)
    return len(A & B) / max(1, len(A | B))


@dataclass
class GeneratedItem:
    question: PaperQuestion
    cluster: int
    candidates_tried: int
    rejected: dict[str, int]
    scores: dict[str, float]
    nearest_history_sim: float
    nearest_history_id: str
    bloom_pred: int | None
    verb_level: int
    critic: dict | None
    exemplar_ids: list[str]
    prompt_version: str
    model: str
    latency_s: float
    fallback_used: bool = False


@dataclass
class GeneratedPaper:
    blueprint: Blueprint
    items: list[GeneratedItem]
    allocation_report: dict
    stats: dict = field(default_factory=dict)

    @property
    def questions(self) -> list[PaperQuestion]:
        return [i.question for i in self.items]


def _exemplars(profile: HistoryProfile, cluster: int, k: int = 5) -> list[dict]:
    c = profile.clusters[cluster]
    by_id = {q["question_id"]: (q, e) for q, e in zip(profile.questions, profile.embeddings)}
    members = [by_id[m] for m in c.member_ids if m in by_id]
    members.sort(key=lambda qe: -float(qe[1] @ c.centroid))
    return [q for q, _ in members[:k]]


def _exemplar_block(ex: list[dict]) -> str:
    lines = [f"- ({int(q['marks']):d} marks, L{q['rbt'][0][1]}) {q['text'][:260]}" for q in ex]
    return wrap_untrusted("reference questions from previous papers of this course", "\n".join(lines))


def generate_paper(bp: Blueprint, profile: HistoryProfile, alloc: Allocation, client: OllamaClient,
                   classifier: LevelClassifier | None, *, use_critic: bool = True,
                   progress: Callable[[str, int, int], None] | None = None) -> GeneratedPaper:
    if not client.is_available():
        raise LLMUnavailableError(f"LLM '{client.model}' is not reachable — start Ollama and pull the model.")
    rng = np.random.default_rng(bp.seed)
    hist_emb = profile.all_embeddings if profile.all_embeddings is not None else profile.embeddings
    hist_q = profile.all_questions or profile.questions            # copy detection sees EVERY historical question
    hist_ids = [q["question_id"] for q in hist_q]
    hist_txt = [q["text"] for q in hist_q]
    selected_emb: list[np.ndarray] = []
    items: list[GeneratedItem] = []
    total = len(alloc.slots)

    for n_done, slot in enumerate(alloc.slots):
        if progress:
            progress(f"Q{slot.item}{slot.part or ''}", n_done, total)
        t0 = time.time()
        cluster = profile.clusters[slot.cluster]
        ex = _exemplars(profile, slot.cluster)
        user = prompts.generation_user(bp.course_name.title(), slot.co, bp.outcomes[slot.co], slot.level, slot.marks,
                                       cluster.keywords[:5], _exemplar_block(ex),
                                       covered=[" ".join(i.question.text.split()[:9]) + "…" for i in items[-12:]])
        rejected: dict[str, int] = {}
        cands: list[Candidate] = []
        embs = np.zeros((0, hist_emb.shape[1]), dtype=np.float32)
        co_emb = encode([bp.outcomes[slot.co]])[0]
        lo, hi = word_range(slot.marks)
        scored: list = []
        feedback = ""
        for attempt in range(3):          # adaptive resampling: tell the model WHY earlier candidates were rejected
            round_user = user if not feedback else user.replace("Write the question now.", feedback + "\nWrite the question now.")
            new_cands: list[Candidate] = []
            for j in range(bp.candidates_per_slot):
                try:
                    raw = client.chat_json(prompts.GENERATION_SYSTEM, round_user, temperature=0.85 + 0.1 * attempt,
                                           seed=int(rng.integers(1, 10**6)), max_tokens=500)
                    new_cands.append(Candidate.model_validate(raw))
                except (LLMOutputError, ValidationError, TypeError):
                    rejected["malformed_output"] = rejected.get("malformed_output", 0) + 1
            if not new_cands:
                if attempt == 2 and not cands:
                    raise LLMOutputError(f"No valid candidate for Q{slot.item}{slot.part or ''} after {3 * bp.candidates_per_slot} tries")
                continue
            base = len(cands)
            cands.extend(new_cands)
            new_embs = encode([c.question for c in new_cands])
            embs = np.vstack([embs, new_embs]) if len(embs) else new_embs
            probs = (classifier.predict_proba([c.question for c in cands], [slot.marks] * len(cands))
                     if classifier is not None else None)
            round_reasons: dict[str, int] = {}
            for i in range(base, len(cands)):
                c = cands[i]
                sims = hist_emb @ embs[i]
                j = int(np.argmax(sims))
                max_sim = float(sims[j])
                n_words = len(c.question.split())
                within = max((float(e @ embs[i]) for e in selected_emb), default=0.0)
                reason = None
                if max_sim > bp.novelty_max_similarity or jaccard_3gram(c.question, hist_txt[j]) > 0.45:
                    reason = "not_novel"
                elif _FIGURE_REF.search(c.question):
                    reason = "refers_to_missing_figure"
                elif not (lo <= n_words <= hi):
                    reason = "length_for_marks"
                elif within > 0.72:
                    reason = "duplicate_within_paper"
                if reason:
                    rejected[reason] = rejected.get(reason, 0) + 1
                    round_reasons[reason] = round_reasons.get(reason, 0) + 1
                    continue
                vl = verb_level(c.question)
                p_level = float(probs[i][slot.level - 1]) if probs is not None else 0.0
                # The verb-lexicon check is the deployed level signal: it measurably outperformed every learned
                # classifier on held-out subjects (docs/EVALUATION_BLOOM.md). A learned classifier is used only
                # if one is explicitly supplied.
                verb_fit = 1.0 if vl == slot.level else (0.5 if abs(vl - slot.level) == 1 else 0.0)
                level_fit = (0.6 * p_level + 0.4 * verb_fit) if probs is not None else verb_fit
                topic_fit = float(embs[i] @ cluster.centroid)
                co_fit = float(embs[i] @ co_emb)
                novelty = 1.0 - max_sim
                length_fit = 1.0 if (lo * 1.3 <= n_words <= hi * 0.8) else 0.6
                score = 0.35 * level_fit + 0.25 * max(topic_fit, 0) + 0.15 * max(co_fit, 0) + \
                    0.15 * min(novelty / 0.4, 1.0) + 0.10 * length_fit
                scored.append((score, i, {"level_fit": level_fit, "topic_fit": topic_fit, "co_fit": co_fit,
                                          "novelty": novelty, "length_fit": length_fit, "total": score},
                               max_sim, hist_ids[j], vl, (int(np.argmax(probs[i])) + 1 if probs is not None else None)))
            if scored:
                break
            feedback = ("Your earlier attempts were REJECTED (" + ", ".join(f"{k}: {v}" for k, v in round_reasons.items()) +
                        "). Write a clearly different question: different sub-topic, different wording, and avoid the themes "
                        "already used in this paper and the reference questions.")
        fallback = False
        if not scored:   # everything filtered after 3 rounds: keep the least-bad candidate but flag it loudly
            fallback = True
            risk = [max(float(np.max(hist_emb @ e)), max((float(x @ e) for x in selected_emb), default=0.0)) for e in embs]
            i = int(np.argmin(risk))
            sims = hist_emb @ embs[i]
            j = int(np.argmax(sims))
            probs = (classifier.predict_proba([c.question for c in cands], [slot.marks] * len(cands))
                     if classifier is not None else None)
            scored = [(0.0, i, {"total": 0.0}, float(sims[j]), hist_ids[j], verb_level(cands[i].question),
                       (int(np.argmax(probs[i])) + 1 if probs is not None else None))]
        scored.sort(key=lambda s: -s[0])

        chosen, critic = None, None
        for rank, s in enumerate(scored[:3]):
            if not use_critic:
                chosen = s
                break
            critic = _critic(client, bp, slot, cands[s[1]].question)
            bad = critic is not None and (critic.get("needs_missing_data") or critic.get("answerable") is False
                                          or critic.get("out_of_scope"))
            if not bad:
                chosen = s
                break
            rejected["critic_rejected"] = rejected.get("critic_rejected", 0) + 1
        if chosen is None:           # all top candidates rejected by the moderator: keep best, flag for the teacher
            chosen, fallback = scored[0], True
        score, i, parts, max_sim, nid, vl, bpred = chosen
        selected_emb.append(embs[i])
        items.append(GeneratedItem(
            question=PaperQuestion(slot.section, slot.item, slot.part, cands[i].question, slot.marks, slot.co, slot.level),
            cluster=slot.cluster, candidates_tried=len(cands), rejected=rejected, scores=parts,
            nearest_history_sim=max_sim, nearest_history_id=nid, bloom_pred=bpred, verb_level=vl, critic=critic,
            exemplar_ids=[q["question_id"] for q in ex], prompt_version=prompts.GENERATION_VERSION,
            model=client.model, latency_s=time.time() - t0, fallback_used=fallback))
    if progress:
        progress("done", total, total)
    return GeneratedPaper(bp, items, alloc.report, {"llm_calls": len(client.calls),
                                                    "llm_seconds": float(sum(c.latency_s for c in client.calls))})


def _critic(client: OllamaClient, bp: Blueprint, slot: Slot, question: str) -> dict | None:
    try:
        out = client.chat_json(prompts.CRITIC_SYSTEM, prompts.critic_user(bp.course_name.title(), bp.outcomes[slot.co],
                                                                         slot.marks, question), temperature=0.0, max_tokens=150)
        return {k: out.get(k) for k in ("answerable", "ambiguous", "needs_missing_data", "out_of_scope", "issue")}
    except (LLMOutputError, LLMUnavailableError):
        return None
