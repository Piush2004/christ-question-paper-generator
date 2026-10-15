"""Aggregate results/generation/generation_eval.json -> results/generation/generation_report.md

Primary evidence = deterministic / verifiable metrics. LLM-judge scores are printed in a separate DIAGNOSTIC section
(the judge was shown to prefer LLM-written text over real faculty questions, so it is not quality evidence)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "results" / "generation" / "generation_eval.json").read_text())
R = d["results"]
systems = ["bank_copy", "llm_only", "rag_slots", "full_no_critic", "full"]
kinds = ["same_course_temporal", "related_course_transfer"]


def runs(system, kind=None, fam=None):
    return [r for r in R if r["system"] == system and (kind is None or r["kind"] == kind) and (fam is None or r["family"] == fam)]


def ms(rs, key):
    v = [r[key] for r in rs if r.get(key) is not None]
    return f"{np.mean(v):.2f} ± {np.std(v, ddof=1) if len(v) > 1 else 0:.2f}" if v else "n/a"


L = ["# Generation comparison — measured results (replicated)", "",
     f"Targets (newest paper held out; systems see only the history family): "
     + "; ".join(sorted({f"{r['family']} [{r['kind']}] history={r['history_family']}" for r in R})) + ". "
     f"RBT mark-share target {d['bloom_target']}. Seeds 7/11/13 (full_no_critic: seed 7 only). Generator `{d['model']}`. "
     "A *run* = one (system, subject, seed). All LLM responses are recorded in `results/generation/llm_cache.jsonl`, so every run can be replayed exactly.", ""]
for kind in kinds:
    rs_k = [r for r in R if r["kind"] == kind]
    if not rs_k:
        continue
    L += [f"## {kind}", "",
          "| system | runs approvable | questions produced/asked | CO coverage | Bloom TV ↓ (mean ± SD over runs) | novelty ↑ | near-copy rate ↓ | LLM-level agreement | format round-trip |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in systems:
        rs = runs(s, kind)
        if not rs:
            continue
        L.append(f"| {s} | {sum(r['approvable'] for r in rs)}/{len(rs)} | {sum(r['n_questions'] for r in rs)}/{sum(r['expected_questions'] for r in rs)} | "
                 f"{ms(rs, 'co_coverage')} | {ms(rs, 'bloom_tv_distance_to_target')} | {ms(rs, 'novelty_mean')} | {ms(rs, 'near_copy_rate')} | "
                 f"{ms(rs, 'level_agreement_llm')} | {sum(r['format_roundtrip_ok'] for r in rs)}/{len(rs)} |")
    L.append("")
L += ["## Per run (subject × seed)", "", "| subject | seed | system | approvable | failed hard checks | q | CO cov | Bloom TV | novelty | near-copy | fmt |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in sorted(R, key=lambda r: (r["family"], r["seed"], systems.index(r["system"]))):
    L.append(f"| {r['family']} | {r['seed']} | {r['system']} | {r['approvable']} | {', '.join(r['hard_failures']) or '-'} | {r['n_questions']}/{r['expected_questions']} | "
             f"{r['co_coverage']:.2f} | {r['bloom_tv_distance_to_target']:.2f} | {r['novelty_mean']:.2f} | {r['near_copy_rate']:.2f} | {r['format_roundtrip_ok']} |")
fl = {s: [r.get("flagged_for_teacher") for r in runs(s) if r.get("flagged_for_teacher") is not None] for s in ("full", "full_no_critic")}
L += ["", "## Questions flagged for teacher attention (every candidate failed a check)", ""]
for s, v in fl.items():
    L.append(f"- {s}: {sum(v)} flagged over {len(v)} runs ({sum(r['n_questions'] for r in runs(s))} questions)")
L += ["", "## DIAGNOSTIC ONLY — LLM-judge scores (1–5, same 7B model; NOT human ratings, NOT quality evidence)", "",
      "| system | clarity | answerable | syllabus fit |", "|---|---|---|---|"]
for s in systems:
    rs = runs(s)
    L.append(f"| {s} | " + " | ".join(f"{np.mean([r['judge'][k] for r in rs if r['judge']]):.2f}" for k in ("clarity", "answerable", "syllabus_fit")) + " |")
ref = d["judge_reference_real_heldout"]
L.append("| *real held-out faculty questions* | " + " | ".join(f"{np.mean([v[k] for v in ref.values() if v]):.2f}" for k in ("clarity", "answerable", "syllabus_fit")) + " |")
L.append("\nThe judge scores real faculty questions below every generated paper, so it rewards LLM-style prose rather than assessment quality.")
(ROOT / "results" / "generation" / "generation_report.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
