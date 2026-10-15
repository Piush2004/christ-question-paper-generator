"""End-to-end orchestration used by the CLI and the evaluation harness:
history profile -> blueprint check -> constraint allocation -> candidate generation + ranking + critic ->
deterministic validation -> PDF/DOCX/JSON export (versioned, never overwritten)."""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path

import numpy as np

from src.bloom.classifier import MODEL_PATH, BloomClassifier
from src.generation.blueprint import Blueprint, default_blueprint, family_of, load_papers, load_questions
from src.generation.generator import GeneratedPaper, generate_paper
from src.generation.render import render_docx, render_pdf
from src.generation.topics import HistoryProfile, build_history
from src.generation.validate import summarize, validate_paper
from src.llm.ollama import OllamaClient
from src.optimization.allocator import allocate

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "outputs" / "papers"


def paper_order(papers: list[dict], family: str) -> list[str]:
    ps = [p for p in papers if p["course_family"] == family]
    ps.sort(key=lambda p: (p["academic_year"], 0 if any(m in (p["exam_session"] or "").lower() for m in ("nov", "dec", "oct")) else 1))
    return [p["paper_id"] for p in ps]


def history_for(family: str, papers: list[dict], questions: list[dict], exclude_paper_ids: set[str] | None = None,
                seed: int = 7) -> HistoryProfile:
    exclude = exclude_paper_ids or set()
    order = [p for p in paper_order(papers, family) if p not in exclude]
    qs = [q for q in questions if q["course_family"] == family and q["paper_id"] not in exclude]
    prior_pool = [q for q in questions if q["paper_id"] not in exclude]
    return build_history(qs, family, order, prior_pool, seed=seed, source_status=load_source_status())


def load_source_status() -> dict[str, str]:
    f = ROOT / "data" / "processed" / "source_quality.json"
    return {k: v["status"] for k, v in json.loads(f.read_text()).items()} if f.exists() else {}


def load_classifier(enabled: bool = False) -> BloomClassifier | None:
    """The learned Bloom classifier is OFF by default: on held-out subjects it did not beat the verb-lexicon
    rule (see docs/EVALUATION_BLOOM.md), so ranking uses the rule. Enable explicitly for experiments."""
    return BloomClassifier.load() if enabled and MODEL_PATH.exists() else None


def next_version_dir(code: str, session: str) -> tuple[Path, int]:
    base = OUT_ROOT / f"{code}_{session.replace(' ', '')}"
    v = 1
    while (base / f"v{v}").exists():
        v += 1
    d = base / f"v{v}"
    d.mkdir(parents=True)
    return d, v


def constraint_provenance(bp: Blueprint, profile: HistoryProfile, it) -> dict:
    """Which requirement behind this question is HARD (supplied by the teacher / blueprint and enforced), which is a
    SOFT target (optimised, deviation reported), and which is only a PREFERENCE derived from unverified historical
    data. Nothing here claims the historical RBT/topic labels are ground truth."""
    level_src = ("SOFT target — teacher-supplied RBT mark-share (deviation reported, tolerance ±max(2 marks, 5%))"
                 if bp.bloom_target else "SOFT target — course's historical marks→level pattern (paper-setter labels, noisy)")
    co_src = ("HARD coverage (every CO examined) + per-slot choice made by the solver; share is a SOFT target from "
              + ("teacher co_weights" if bp.co_weights else "historical CO mark share"))
    return {
        "section_structure_and_marks": "HARD — blueprint (teacher-supplied), enforced by validation",
        "course_outcome": co_src,
        "rbt_level": level_src + "; level wording checked by verb lexicon (measured best level predictor, still weak)",
        "topic": f"PREFERENCE — unsupervised cluster of past questions '{profile.clusters[it.cluster].label}'; "
                 "NOT a verified syllabus topic",
        "originality": "HARD filter vs every historical question (embedding, 3-gram) + HARD validation of the finished paper",
    }


def export(paper: GeneratedPaper, profile: HistoryProfile, out_dir: Path, version: int, *, draft: bool = True,
           validation: dict | None = None, timings: dict | None = None) -> dict:
    bp = paper.blueprint
    pdf = render_pdf(bp, paper.questions, out_dir / "paper.pdf", draft=draft)
    docx = render_docx(bp, paper.questions, out_dir / "paper.docx", draft=draft)
    meta = {
        "version": version, "course_code": bp.course_code, "exam_session": bp.exam_session,
        "status": "DRAFT — teacher review required", "blueprint": json.loads(bp.to_json()),
        "allocation": paper.allocation_report, "validation": validation, "timings": timings, "stats": paper.stats,
        "questions": [{
            "section": it.question.section, "item": it.question.item, "part": it.question.part,
            "text": it.question.text, "marks": it.question.marks, "co": it.question.co, "level": it.question.level,
            "topic_cluster": profile.clusters[it.cluster].label, "scores": it.scores,
            "nearest_history_question": it.nearest_history_id, "nearest_history_similarity": round(it.nearest_history_sim, 3),
            "bloom_classifier_prediction": it.bloom_pred, "verb_level": it.verb_level, "moderator": it.critic,
            "candidates_tried": it.candidates_tried, "rejected_candidates": it.rejected,
            "reference_questions": it.exemplar_ids, "prompt_version": it.prompt_version, "model": it.model,
            "flagged_for_teacher": it.fallback_used,
            "slot_id": f"{it.question.section}{it.question.item}{it.question.part or ''}",
            "constraint_provenance": constraint_provenance(bp, profile, it),
        } for it in paper.items],
    }
    (out_dir / "paper.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pdf": str(pdf), "docx": str(docx), "json": str(out_dir / "paper.json")}


def run(course: str, session: str, *, bp_overrides: dict | None = None, model: str = "qwen2.5:7b-instruct-q4_K_M",
        use_critic: bool = True, draft: bool = True, progress=None) -> dict:
    papers, questions = load_papers(), load_questions()
    family = family_of(course, papers)
    bp = default_blueprint(course, session, papers=papers, questions=questions)
    for k, v in (bp_overrides or {}).items():
        setattr(bp, k, v)
    t0 = time.time()
    profile = history_for(family, papers, questions, seed=bp.seed)
    t_hist = time.time() - t0
    t0 = time.time()
    alloc = allocate(bp, profile)                       # raises InfeasibleBlueprint with reasons
    t_alloc = time.time() - t0
    client = OllamaClient(model=model)
    t0 = time.time()
    paper = generate_paper(bp, profile, alloc, client, load_classifier(), use_critic=use_critic, progress=progress)
    t_gen = time.time() - t0
    checks = validate_paper(bp, paper.questions, [q["text"] for q in (profile.all_questions or profile.questions)],
                            profile.all_embeddings if profile.all_embeddings is not None else profile.embeddings)
    summary = summarize(checks)
    out_dir, version = next_version_dir(bp.course_code, session)
    files = export(paper, profile, out_dir, version, draft=draft, validation=summary,
                   timings={"history_s": t_hist, "allocation_s": t_alloc, "generation_s": t_gen})
    return {"files": files, "validation": summary, "allocation": alloc.report, "version": version,
            "timings": {"history_s": t_hist, "allocation_s": t_alloc, "generation_s": t_gen}, "paper": paper}
