# Question Paper Intelligence — Christ University

A curriculum-aware, constraint-controlled question-paper generator for CHRIST (Deemed to be University)
end-semester exams, with a measured evaluation harness. It is **teacher-assistance software**: every paper
it produces is a draft that a faculty member must review and approve.

## What works today (verified by tests and measured runs)

| Capability | State | Evidence |
|---|---|---|
| Parse real CHRIST papers (two layouts) into structured questions with marks, CO, RBT level, sections | **Working** — all 13 admitted papers reconcile with their own printed totals | `src/extraction/christ_parser.py`, `tests/test_christ_parser.py` |
| Dataset: 13 papers / 298 labelled questions / 10 BCA courses (corrected grouping) with per-question source-quality status | **Built**, leakage-safe protocols; 21 questions (7%) have extraction defects, 105 more are LLM-flagged for human review (uncalibrated) | `docs/DATASET_ANALYSIS.md`, `docs/VALIDITY_AUDIT.md` |
| Bloom (RBT) classification | **Measured; no learned model beats the verb rule** on unseen subjects (labels are inconsistent) | `docs/EVALUATION_BLOOM.md` |
| Constraint allocator (CP-SAT): CO coverage, RBT mix, topic spread, OR-pairs; rejects impossible blueprints with reasons | **Working** | `src/optimization/allocator.py`, `tests/test_allocator.py` |
| LLM candidate generation + novelty filter + ranking + moderator critic + adaptive resampling | **Working** (local Ollama, Qwen2.5-7B) | `docs/GENERATION_ENGINE.md` |
| Deterministic paper validation (marks, items, OR structure, CO coverage, duplicates, copy-from-history) | **Working** | `src/generation/validate.py`, `tests/test_validate.py` |
| PDF + DOCX in the real CHRIST layout, identical template for every paper, enforced by a re-parse round-trip test | **Working** | `src/generation/render.py`, `tests/test_generation_format.py` |
| Baseline comparison (bank copy / LLM-only / retrieval-only / full): 2 same-course temporal hold-outs + 1 related-course transfer, 3 seeds, exact-replay cache | **Pilot, replicated**; no human evaluation | `docs/EVALUATION_GENERATION.md`, `docs/VALIDITY_AUDIT.md` |

## Generate a paper

```powershell
# Ollama must be running with the model pulled:  ollama pull qwen2.5:7b-instruct-q4_K_M
.venv\Scripts\python.exe scripts/generate_paper.py --course BCA202-3 --session "November 2025"
.venv\Scripts\python.exe scripts/generate_paper.py --course graph_theory --session "April 2026" --bloom 2:0.3,3:0.4,4:0.3
.venv\Scripts\python.exe scripts/generate_paper.py --course BCA201-3 --session "April 2026" --sections A:10x2,B:6x5:2,C:5x10:1
```
Output: `outputs/papers/<course>_<session>/v<N>/paper.pdf | paper.docx | paper.json` (new version each run, never overwritten). `paper.json` carries per-question provenance and the validation verdict; an invalid blueprint is refused with reasons before any model call. Add `--final` only after teacher approval to drop the DRAFT footer.

## Rebuild data and rerun experiments

```powershell
.venv\Scripts\python.exe scripts/build_dataset.py              # parse + verify papers -> data/processed/
.venv\Scripts\python.exe scripts/analyze_dataset.py            # docs/DATASET_ANALYSIS.md + figures
.venv\Scripts\python.exe scripts/train_bloom.py --skip-llm     # leave-one-subject-out Bloom comparison
.venv\Scripts\python.exe -m scripts.eval_bloom_leave_paper_out
.venv\Scripts\python.exe -m scripts.eval_bloom_llm
.venv\Scripts\python.exe -u scripts/eval_generation.py all     # held-out generation comparison (~1.5 h on an RTX 5060)
.venv\Scripts\python.exe -m pytest tests -q                    # full test suite
```
Add papers: drop PDFs into `Question Papers/` and rerun `build_dataset.py` — a paper is admitted only if the parser can verify it; rejections are listed with reasons in `data/processed/build_report.json`.

## Honest limits

- **Small data**: 298 questions, 13 papers, one programme; only graph theory (3 papers) and discrete mathematics (2) have more than one paper of the same course. Nothing here supports claims about other programmes.
- **Experiment status**: a validity audit (`docs/VALIDITY_AUDIT.md`) corrected earlier errors (mixed courses, wording, reproducibility explanation); results are a replicated *pilot* with no significance tests.
- **Labels are teacher assertions.** The RBT labels are inconsistent enough that trained classifiers failed to beat a hand-written verb rule; no Bloom model is deployed.
- **No difficulty, DOK, unit/topic labels and no student-response data exist**, so none of those models/psychometrics were built; claiming them would be fabrication.
- **No human evaluation yet.** Generation quality was measured with deterministic checks; the LLM judge is diagnostic only (it scores real faculty questions below generated ones), so content quality is unverified.
- **Local-LLM output is state-dependent**: a fresh re-run does not exactly reproduce a recorded run; recorded responses are replayable from `results/generation/llm_cache.jsonl`. The 7B local model still writes some ambiguous or numerically unsound questions — teacher review is mandatory.
- **Topics are unsupervised clusters of past questions**, not official syllabus units; no syllabus document was available.
- OCR is unavailable (no Tesseract); scanned papers are not ingested.
- Math notation is partly lost in PDF text extraction.

## Layout

```
Question Papers/   papers supplied by the project owner (source of truth)
data/              raw / interim / processed (questions.jsonl, papers.jsonl, build_report.json)
src/extraction/    christ_parser.py (layout-aware) + older generic rule engine
src/bloom/         verb lexicon (deployed level check), experimental classifier
src/optimization/  CP-SAT allocator
src/generation/    blueprint, topics, generator, validate, render, baselines, pipeline
src/llm/           Ollama client (JSON mode, retries, untrusted-text delimiting)
scripts/           build_dataset, analyze_dataset, train_bloom, eval_*, generate_paper
results/           classification/ generation/ figures/
outputs/           generated paper drafts (papers/) and evaluation PDFs (eval/) — regenerable, safe to delete
docs/              evaluation reports, generation engine, dataset analysis, decision log, audits
```

Earlier documents (`PHASE_0_5_AUDIT.md`, `ENVIRONMENT_AUDIT.md`, `LITERATURE_BASELINE.md`, `RESEARCH_GAP.md`, `ARCHITECTURE.md`) describe the pre-data foundation phase and the research positioning; where they say "no dataset yet" they predate this work.
