# Generation evaluation — what was measured, what it shows, what it does not

**Status: preliminary pilot** — 2 same-course temporal hold-outs + 1 related-course transfer case, 3 seeds, one 7B local model, no human raters, no significance tests. Read together with `docs/VALIDITY_AUDIT.md`, which also lists corrections to an earlier version of this report (course grouping, "subject-held-out" wording, the reproducibility explanation, and the judge).

Raw data: `results/generation/generation_eval.json`; full tables: `results/generation/generation_report.md` (`scripts/summarize_generation.py`); generated PDFs: `outputs/eval/`. All LLM responses are recorded in `results/generation/llm_cache.jsonl` and can be replayed exactly. Superseded runs: `generation_eval_pre_audit_mixed_families.json`, `generation_eval_v1_generator_partial.json`.

## Design

**Temporal hold-out within a course.** The newest paper is held out and each system sees only the older papers of the same course as history:
- **discrete mathematics** — held out BCA101-2 (Apr 2025); history: 1 paper (BCA104-2, Apr 2024; 24 questions, 3 topic clusters)
- **graph theory** — held out BCA201-4 (Apr 2025); history: 2 papers (49 questions, 6 clusters)
- **related-course transfer (labelled separately)** — PSD-II (BCA302-4, Apr 2025) generated from PSD-I history (13 questions); a *different course* of the same series, not a same-subject test.

Blueprint = the structure and COs of the previous paper; requested RBT mark shares L2 30% / L3 40% / L4 30%. This is **not** subject-held-out and the held-out paper's structure is not what the blueprint copies.

**Systems:** `bank_copy` (random past questions) · `llm_only` (one prompt for the whole paper) · `rag_slots` (per-question LLM with retrieved exemplars, CO round-robin, level sampled from the target, one candidate, no solver/ranking/critic) · `full_no_critic` (CP-SAT allocation → 4 candidates/slot with up to 3 resampling rounds → hard filters → ranking) · `full` (+ moderator critic). Seeds 7, 11, 13 (`full_no_critic`: seed 7 only). A *run* is one (system, target, seed).

**Metrics (identical code for every system).** Deterministic validator hard checks (`approvable`); questions produced vs asked; CO coverage; total-variation distance between achieved and requested RBT mark shares; novelty and near-copy rate against history; level agreement with an independent zero-shot LLM classifier; format round-trip (rendered PDF re-parses to the blueprint). The LLM-judge is diagnostic only (below).

## Results — same-course temporal (2 courses × 3 seeds = 6 runs per system)

| system | runs approvable | questions produced/asked | CO coverage | Bloom TV ↓ | novelty ↑ | near-copy ↓ | LLM level agreement | format round-trip |
|---|---|---|---|---|---|---|---|---|
| bank_copy | 0/6 | 147/147 | 0.90 ± 0.11 | 0.23 ± 0.09 | 0.00 | 1.00 | 0.30 ± 0.09 | 6/6 |
| llm_only | 0/6 | **95/147** | 0.89 ± 0.17 | 0.28 ± 0.08 | 0.50 ± 0.09 | 0.01 ± 0.03 | 0.24 ± 0.16 | **0/6** |
| rag_slots | 1/6 | 147/147 | 1.00 | 0.14 ± 0.05 | 0.37 ± 0.07 | 0.06 ± 0.06 | 0.49 ± 0.06 | 5/6 |
| full_no_critic | 2/2 | 49/49 | 1.00 | 0.00 | 0.43 ± 0.03 | 0.00 | 0.55 ± 0.04 | 2/2 |
| **full** | **6/6** | 147/147 | 1.00 | 0.00 | 0.43 ± 0.03 | 0.00 | 0.52 ± 0.07 | 6/6 |

## Results — related-course transfer (PSD-I → PSD-II, 3 seeds)

| system | runs approvable | questions | CO cov | Bloom TV | novelty | near-copy | LLM level agreement | format |
|---|---|---|---|---|---|---|---|---|
| bank_copy | 0/3 | 39/39 | 1.00 | 0.42 ± 0.09 | 0.00 | 1.00 | 0.41 ± 0.12 | 3/3 |
| llm_only | 0/3 | 22/39 | 0.89 ± 0.19 | 0.40 ± 0.10 | 0.54 ± 0.02 | 0.00 | 0.00 | 0/3 |
| rag_slots | 1/3 | 39/39 | 1.00 | 0.16 ± 0.07 | 0.39 ± 0.04 | 0.15 ± 0.08 | 0.62 ± 0.13 | 3/3 |
| full_no_critic | 1/1 | 13/13 | 1.00 | 0.00 | 0.41 | 0.00 | 0.69 | 1/1 |
| **full** | **3/3** | 39/39 | 1.00 | 0.00 | 0.42 ± 0.01 | 0.00 | 0.72 ± 0.04 | 3/3 |

(± = SD over runs; with 3–6 runs this is a rough spread, not an interval.)

## What the evidence supports

1. **Structural reliability.** `full` produced a validator-approvable, correctly formatted paper in **9 of 9** runs; `rag_slots` in 2 of 9 (failures: duplicated questions, dangling references, near-copies, empty questions); `llm_only` in **0 of 9** — it returned between 3 and 28 questions against the 13–25 asked, wrong marks totals, missing outcomes, and output that never re-parsed into the paper format (0/9); `bank_copy` 0/9 (every question is a copy; OR-alternatives and outcome coverage fail).
2. **Originality.** The full system produced no exact, normalised or 3-gram matches to any historical question and none at MiniLM cosine ≥ 0.80 (pooled 9 runs); five similarity levels are reported in `docs/VALIDITY_AUDIT.md` §Q9 (any level: 0.9% of full-system questions vs 4.0% for retrieval-only).
3. **Replicability of the structural result**: consistent over 3 seeds and 3 targets, with no run of `full` failing a hard check.

## What it does not show

- **"Approvable" is partly circular.** The full system is constructed to satisfy those checks; the baselines are not. It demonstrates that baselines cannot be relied on to satisfy a blueprint — not that the full system's questions are better.
- **No evidence on content quality.** No faculty rated any question. The LLM judge (same 7B model) scores real faculty questions lowest (clarity 2.91, answerable 3.26, syllabus-fit 4.11) and every generated paper higher (clarity 3.57–3.89, answerable 4.21–4.38); it rewards LLM prose and is reported only as a **diagnostic** in `generation_report.md`.
- **Cognitive control is not clearly better than prompting.** Independent LLM level agreement: `full` 0.52 (same-course) / 0.72 (transfer) vs `rag_slots` 0.49 / 0.62, with spreads of ±0.06–0.13; and the same classifier agrees with faculty labels on real questions only ~0.32 of the time.
- **The critic's effect is unmeasured**: `full` and `full_no_critic` share cached candidate generation and differ only when the critic rejects a candidate.
- **Novelty is relative.** 25% of the real held-out graph-theory paper is itself flagged against its history, i.e. faculty reuse questions far more than this system allows; zero near-copies does not mean zero concept repetition.
- Very small histories (1 paper for discrete maths and PSD-I), 3 seeds, no significance tests, one model.

## Manual reading of generated papers (informal, by the assistant — not faculty review)

- **Graph theory, full (seed 7)**: coherent; some 3-mark items demand too much (Huffman coding with five frequencies plus average code length); one question ended with "…given the following road network data:" and no data, which the validator missed. The validator's self-containment check was extended afterwards (`tests/test_validate.py`); **runs in this report used the extended check**.
- **Discrete mathematics, full (seed 7)**: concrete and answerable (much better than the earlier mixed-history version), but more than half of the 24 questions are about relations/matrices, several near-templated; CO text sometimes echoed into stems.
- **PSD-II, full**: plausible; several 2-mark L4 items ("Analyse the differences between X and Y…, with examples") are too heavy for the marks.
- 5 of 186 `full` questions over 9 runs were flagged for the teacher (every candidate failed a check).

## Conclusions

The constraint-first pipeline is justified on **reliability** grounds (valid structure, format, originality) and the evidence for that is replicated but small and partly by construction. Content quality, cognitive validity and syllabus alignment are **unverified** until faculty rate generated vs real questions. Teacher review remains mandatory; nothing is auto-approved.

Next steps, by expected value: (1) faculty rating of ~50 generated vs ~50 real questions (≥2 raters) to replace the judge and calibrate the novelty thresholds; (2) more same-course papers per course (the binding constraint on every experiment here); (3) a stronger generator through a second provider client; (4) per-mark-band scope control; (5) significance tests once ≥ 5 courses have history.

## Reproduce

```powershell
.venv\Scripts\python.exe -u scripts/eval_generation.py all      # resumable, ~2-3 h; replays recorded responses where available
.venv\Scripts\python.exe scripts/summarize_generation.py
.venv\Scripts\python.exe scripts/audit_leakage.py
```
