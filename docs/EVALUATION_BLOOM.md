# Bloom (RBT) classification — measured results

All numbers come from `scripts/train_bloom.py`, `scripts/eval_bloom_leave_paper_out.py`, `scripts/eval_bloom_llm.py` and `scripts/audit_labels.py` (raw outputs in `results/classification/` and `results/audit/`). Nothing here is estimated or carried over from another dataset.

**Revision note.** An earlier version of this report grouped Foundational Mathematics with Discrete Mathematics and PSD-I with PSD-II as single "subjects" (8 families). The validity audit (`docs/VALIDITY_AUDIT.md`) found these are different courses; families were corrected (10 families) and every leave-one-subject-out number below was recomputed. The conclusions did not change; the pre-fix numbers are kept in `results/classification/bloom_metrics_pre_family_fix.json`.

## Task and labels

Predict the Revised-Bloom level (L1–L6) printed next to each question. The labels are the **paper setters' own judgement** (297 questions with ≥3 words, 13 papers, 10 courses). Class counts: L1 58 · L2 73 · L3 80 · L4 50 · L5 27 · L6 9. These are teacher assertions, not verified ground truth.

## Protocols (leakage control)

- **A. Leave-one-subject-out** (10 folds, one per course). A course's questions from *all* years are either all train or all test — the same question re-asked in another year, and course vocabulary, cannot leak. Measures transfer to an unseen course.
- **B. Leave-one-paper-out with near-duplicate removal** (13 folds). Training may use other years of the same course, but any training question with embedding cosine ≥ 0.85 or word-3-gram Jaccard ≥ 0.5 to a test question is removed first (26 removals in total).
- LLM zero-shot needs no training data, so every question is a true held-out prediction.
- Same data and folds for every model; 95% CIs by bootstrap over questions; paired bootstrap for model-vs-model differences.

## Results — protocol A (unseen course)

| Model | Accuracy [95% CI] | Within ±1 level | Macro-F1 [95% CI] | Weighted-F1 |
|---|---|---|---|---|
| Majority class | 0.246 [0.199, 0.293] | 0.657 | 0.093 [0.072, 0.114] | 0.146 |
| **Verb lexicon rule** (not fitted to the data) | 0.279 [0.226, 0.330] | 0.653 | 0.243 [0.181, 0.302] | 0.260 |
| TF-IDF (word+char) + LR | 0.236 [0.189, 0.283] | 0.603 | 0.165 [0.129, 0.205] | 0.220 |
| MiniLM embedding + LR | 0.219 [0.175, 0.269] | 0.623 | 0.169 [0.127, 0.214] | 0.211 |
| bge-small embedding + LR | 0.236 [0.185, 0.286] | 0.582 | 0.181 [0.137, 0.231] | 0.217 |
| mpnet-base embedding + LR | 0.229 [0.182, 0.276] | 0.603 | 0.184 [0.136, 0.233] | 0.224 |
| MiniLM + marks features + LR | 0.209 [0.162, 0.256] | 0.593 | 0.146 [0.114, 0.179] | 0.200 |
| bge-small + marks + LR | 0.222 [0.175, 0.269] | 0.579 | 0.156 [0.120, 0.187] | 0.202 |
| mpnet-base + marks + LR | 0.215 [0.168, 0.263] | 0.576 | 0.157 [0.123, 0.190] | 0.210 |
| MiniLM **fine-tuned** (end-to-end, 8 epochs, GPU) + marks | 0.256 [0.205, 0.306] | 0.626 | 0.167 [0.131, 0.204] | 0.231 |
| **Qwen2.5-7B zero-shot** (LLM; unaffected by the family fix) | **0.316** [0.266, 0.367] | 0.660 | **0.275** [0.211, 0.334] | 0.310 |

("Within ±1" is dominated by the label distribution: always predicting L3 already gives ≈0.66.)

## Results — protocol B (same-course history allowed, near-duplicates removed)

| Model | Accuracy | Within ±1 | Macro-F1 [95% CI] |
|---|---|---|---|
| Majority | 0.249 | 0.663 | 0.085 [0.067, 0.103] |
| Verb rule | 0.279 | 0.653 | 0.243 [0.182, 0.302] |
| TF-IDF + LR | 0.202 | 0.566 | 0.149 [0.111, 0.187] |
| MiniLM + LR | 0.215 | 0.572 | 0.181 [0.136, 0.227] |
| MiniLM + marks + LR | 0.209 | 0.576 | 0.162 [0.124, 0.195] |

## Label reliability audit (why the models cannot learn this)

- **Test–retest on repeated questions.** Only 8 same-course question pairs recur (cosine ≥ 0.90 or 3-gram Jaccard ≥ 0.6) across different papers — all in graph theory. **Exact RBT agreement 4/8 (50%)**, within ±1 6/8, Cohen's κ = 0.29, mean |difference| 0.75 levels. E.g. an identical "Explain Prim's algorithm and use it to obtain the minimal spanning tree…" is L2 in one paper and L4 in another; "Explain the isomorphism of graphs…" is L5 vs L3. n = 8, all from one course, so this is suggestive, not a reliability coefficient.
- **Same verb, many levels.** Leading-verb label spread (label entropy in bits; marginal label entropy is 2.37): *what* (n=27) L1×6 L2×10 L3×4 L4×2 L5×5, entropy 2.15; *define* (14) L1×2 L2×1 L3×5 L4×4 L5×2, entropy 2.12; *state* (10) L1×5 L2×1 L3×2 L4×1 L5×1; *discuss* (13) L2×4 L3×3 L4×4 L5×1 L6×1. Most verbs carry about as much label uncertainty as the label distribution itself.
- No second rater exists, so inter-annotator agreement cannot be computed. The inconsistency may be setter-specific conventions, genuine item ambiguity, or error — the data cannot distinguish them.

## What this shows (and what it does not)

1. **Every learned classifier is barely above the majority baseline and below the unfitted verb rule.** Paired bootstrap, macro-F1(model) − macro-F1(verb rule): TF-IDF −0.075 [−0.142, −0.009]; MiniLM −0.073 [−0.145, +0.004]; bge-small −0.060 [−0.137, +0.021]; mpnet −0.058 [−0.134, +0.021]; fine-tuned MiniLM −0.074 [−0.142, −0.006]; marks-feature variants −0.084 to −0.095 (CIs exclude 0). Several intervals touch zero because n is small, so "worse than the rule" is firm only for some models. Adding same-course history (protocol B) did not help.
2. **The zero-shot 7B LLM is the best predictor measured** (macro-F1 0.275 vs rule 0.243) but its CI overlaps the rule's and absolute accuracy (0.32) is low. The difference is not established.
3. **Interpretation**: consistent with label inconsistency rather than model weakness — a text model cannot recover a labelling convention that differs between papers (and, per the test–retest sample, sometimes between years for the same question). This is a hypothesis supported by the audit, not proven.
4. **Consequence for the product**: no learned Bloom classifier is deployed. The generator uses the verb-lexicon rule for level checking (`src/bloom/lexicon.py`), and an *independent* zero-shot LLM pass to audit generated questions in the experiments. `src/bloom/classifier.py` and `scripts/fit_bloom_production.py` exist for experiments but the classifier is off by default.
5. **What would change this**: teacher-verified labels on a few hundred questions with ≥2 raters per course (to measure agreement and fit a per-teacher model), or a larger multi-year corpus. Until then claims about Bloom accuracy beyond the numbers above are unsupported.

**Implication for generation.** Because the historical RBT labels are not reliable ground truth, the generator treats RBT level as a *requested target* (teacher-supplied or a soft historical prior), never as evidence that a produced question truly sits at that level. See "Hard / soft / preference" in `docs/GENERATION_ENGINE.md`.

DOK, difficulty, unit and topic have **no labels** in these papers, so no classifiers for them were trained or evaluated.

## Reproduce

```powershell
.venv\Scripts\python.exe scripts\build_dataset.py
.venv\Scripts\python.exe scripts\train_bloom.py --skip-llm
.venv\Scripts\python.exe -m scripts.eval_bloom_leave_paper_out
.venv\Scripts\python.exe -m scripts.eval_bloom_llm
.venv\Scripts\python.exe scripts\audit_labels.py
```
(seed 13; embeddings are cached in `data/processed/`; the LLM run is resumable.)
