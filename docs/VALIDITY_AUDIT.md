# Scientific-validity audit

Scope: *can the claims made so far be trusted?* This audit changed code only where it found a defect. Every number is produced by a script in `scripts/` (outputs in `results/audit/` and `results/`). Two earlier statements of mine were wrong and are corrected here — see §A.

## A. Corrections to earlier claims

1. **"Subject-held-out" was wrong for generation.** The generation experiment is a *temporal hold-out within a course* (newest paper held out, older papers of the same course as history). Only the Bloom classification study is subject-held-out.
2. **Two of three held-out "subjects" were not single courses.** The first design grouped *Foundational Mathematics* (sem I) with *Discrete Mathematics* (sem II), and *PSD-I* (sem I) with *PSD-II* (sem IV). They have different course outcomes, so history, CO shares and CO↔topic statistics were built from mismatched CO ids. Families were corrected (10 families); the test `tests/test_no_leakage.py` now enforces "a family is one course". After the fix only **graph theory (3 papers) and discrete mathematics (2 papers)** admit a same-course temporal hold-out; PSD-I→PSD-II is kept as an explicitly labelled *related-course transfer* case. Evidence base is therefore **2 courses + 1 transfer case**, not 3 courses. Pre-fix results are retained in `results/generation/generation_eval_pre_audit_mixed_families.json` and `results/classification/bloom_metrics_pre_family_fix.json`.
3. **"Ollama is not bit-reproducible / same seed, different outcome" was mis-explained.** The flip I saw was largely a *prompt change* between runs. Measured properly (§Q10) the server's output depends on its internal state, which is a different and real effect.
4. **"A third of the maths questions are ill-posed" referred to *generated* questions**, not the source corpus. The source corpus's defects were not measured at that time; they are now (§Q5).

## B. The twelve questions

**Q1. Can every generated question be traced to an explicit constraint?** Yes, with the right reading of "constraint". `paper.json` now stores per question a `slot_id` and `constraint_provenance` stating which attributes are HARD (blueprint: structure, marks, OR-pairs, CO coverage, originality), which are SOFT targets (RBT share, CO share) and which are only PREFERENCES (topic cluster). The CO and level of each individual slot are *solver decisions* inside those targets, not teacher-specified values unless the teacher gives `co_weights`/`bloom_target`.

**Q2. Are Bloom targets source-grounded?** No. They are either (a) teacher-supplied targets for the new paper (a requirement, not evidence about historical items) or (b) a historical marks→level prior built from the paper setters' RBT labels, which are noisy: exact RBT agreement between repeated identical/near-identical questions is **4/8 (50%)**, Cohen's κ = **0.29** (n = 8 pairs, all graph theory; `results/audit/labels.json`), and the same leading verb spans L1–L5 (docs/EVALUATION_BLOOM.md). No learned Bloom model is deployed, and a requested level is never presented as verified.

**Q3. Where did the topic labels come from?** Nowhere external. Topics are KMeans clusters (k = clamp(n/7, 3..8), seed 7) over MiniLM embeddings of the course's *eligible* past questions, named by their top TF-IDF terms. They are not syllabus units and carry no verification; with one or two historical papers they are coarse (graph theory 6 clusters from 42 usable questions, discrete maths 3 from 23, PSD-I 3 from 13). Clusters and embeddings were verified bit-identical across separate processes. Documented as PREFERENCE-level in `docs/GENERATION_ENGINE.md`.

**Q4. Are the 298 questions suitable as training/evaluation data?** For Bloom training: no, for the label reasons in Q2 (hence the negative result). For use as exemplars / copy-detection / structural statistics: yes with exclusions. Source status (`data/processed/source_quality.json`; original text untouched):
- deterministic checks: **277 VALID, 11 INCOMPLETE** (refers to a figure/graph/table or ends with a colon with no data), **10 EXTRACTION_ERROR** (lost formula text, fragments) = 21/298 (7.0%) with extraction-level defects; graph theory 13/73, discrete maths 5/48.
- adding an LLM screen (Qwen2.5-7B, moderator prompt) raises **105 more to NEEDS_HUMAN_REVIEW** (35%; flags: not-answerable-as-written 103, out-of-scope 68, needs-missing-data 35, ambiguous 16, overlapping). **This screen is uncalibrated** — it flags items like "Generate a 0-level DFD for a specific application domain", and the same model rates real faculty questions below its own output (diagnostic table in the generation report). I treat it as triage, never as a verdict.
- Questions with deterministic defects are excluded from exemplar/cluster material (e.g. graph theory 42 of 49 historical questions remain usable); all questions still take part in copy detection.

**Q5. How many source questions are ill-posed?** *Unknown — it cannot be determined without a human.* Bounds: ≥ 21 (7%) have extraction-level defects; up to 126 (42%) are flagged by one or the other screen, with unknown precision. `ILL_POSED` and `AMBIGUOUS` statuses exist in the schema but are never assigned automatically. The corpus needs faculty adjudication of a sample before any claim here.

**Q6. Does the generator learn formatting instead of assessment structure?** The generator is not trained, so it cannot overfit to format; structure comes from the blueprint and format from one template (re-parse round-trip test). The real risk is different: in the held-out experiment the blueprint is the *previous paper's structure*, so structural compliance is easy by construction. Robustness to unusual structures was tested for the allocator only: 48 randomly shaped blueprints (2–4 sections, 3–10 items, mixed marks, OR-items, explicit Bloom targets), 21 with injected contradictions: all 27 sound blueprints solved and passed an independent verifier (0 unsound solutions), all 21 contradictions rejected with reasons (0 false rejections, 0 wrongly accepted); median solve 0.9 s, max 4.1 s (`results/audit/allocator.json`). LLM generation on novel structures was **not** tested.

**Q7. Are the held-out experiments genuinely held out?** Within their stated design, yes: the evaluation asserts the held-out paper is absent from the history and blueprint, `tests/test_no_leakage.py` checks family/target construction, and generated text was compared with the held-out paper (Q8). Not covered: (a) the 7B model may have seen public CHRIST papers during pre-training (the data bank is public) — unmeasurable here; (b) a single historical paper for discrete maths and PSD-I means very small histories; (c) it is not subject-held-out (see A1).

**Q8. Does retrieval leak held-out questions?** Exemplars are drawn only from history clusters; the held-out paper is excluded by assertion. Empirically, generated questions do not resemble the held-out paper: for `full`, 0 exact/normalised/3-gram matches, MiniLM cosine ≥ 0.80 for 0.5% of questions, mpnet ≥ 0.80 for 0.9% (pooled over 9 runs, `results/audit/leakage.json`).

**Q9. Is novelty semantic rather than exact-string?** Yes, layered: exact, normalised, word-3-gram Jaccard, two embedding models, and a paraphrase cross-encoder on the top-3 neighbours. Pooled over runs, against the history the system saw:

| system | exact/normalised | 3-gram ≥0.45 | MiniLM ≥0.80 | mpnet ≥0.80 | cross-enc ≥0.80 | any level flagged |
|---|---|---|---|---|---|---|
| bank_copy | 100% | 100% | 100% | 100% | 91% | 100% |
| llm_only | 0 | 0 | 0.8% | 0.8% | 2.2% | 2.2% |
| rag_slots | 0 | 0 | 9.2% | 11.6% | 1.3% | 4.0% |
| full_no_critic | 0 | 0 | 0 | 1.3% | 0 | 0 |
| full | 0 | 0 | 0 | 2.2% | 0.9% | 0.9% |

Caveats: thresholds are not validated against human judgements of "too similar"; the TinyBERT cross-encoder is the weakest signal (it scores only 91% of verbatim copies ≥ 0.80); and for calibration, **real faculty re-ask past questions far more than my system tolerates** — 25% of the real held-out graph-theory paper is flagged by one of these levels against its own history. A "no copies" claim means "no match at any of these levels", not "no concept repetition": in the discrete-maths paper I read, more than half of the 24 questions concern relations/matrices, several in near-identical template wording (only 3 topic clusters exist because only one historical paper is available).

**Q10. Why can the same seed produce different outcomes?** Measured (`scripts/audit_determinism*.py`): repeating one request back-to-back gives identical output (8/8, also under 4 concurrent threads), but the *same* request interleaved with other requests produced **3 distinct responses in 5 calls** (`results/audit/determinism_state.json`). Local-LLM output depends on server state (prompt/KV cache), not only on (model, prompt, seed). Consistently, regenerating one recorded run fresh reproduced only 8/25 questions, while **replaying from the recorded-response cache reproduced 25/25** with 100% cache hits (`results/audit/reproduce.json`). Mitigation implemented: `OllamaClient(cache_path=…)` records every response and `replay_only` replays them; all reported generation results are replayable from `results/generation/llm_cache.jsonl`. A *fresh* re-run will not exactly match; statistical replication across seeds is the right way to read variability.

**Q11. Can the full evaluation be repeated multiple times?** Yes: it is resumable and was run with 3 seeds (7, 11, 13) per system per target (full_no_critic: seed 7 only). See `docs/EVALUATION_GENERATION.md` for per-run results and the limits (2 courses + 1 transfer case; no significance tests).

**Q12. Can the automatic judge be removed from the primary evidence?** Done. It appears only in a clearly labelled diagnostic table, because it scores real faculty questions (clarity 2.91, answerable 3.26) below every generated paper (3.57–3.89, 4.21–4.38) and therefore cannot rank quality.

## C. Remaining weaknesses (not fixed)

- **Circularity of "approvable".** The full system is built to satisfy the validator's checks, the baselines are not; "approvable" differences demonstrate that baselines cannot satisfy a blueprint, not that the full system's *content* is better. The RBT-level agreement against an independent LLM classifier (full 0.52/0.72 vs rag_slots 0.49/0.62 for same-course/transfer) is the only non-circular cognition signal and is not clearly different.
- **Critic benefit is unmeasured.** `full` and `full_no_critic` share candidate generation (cached) and differ only when the critic rejects a candidate; no effect can be claimed.
- **No human evaluation of any generated question.** My informal reading (as the assistant, not faculty review) of the discrete-maths paper found concrete, answerable items but heavy repetition of one concept family and CO-text echoed into stems ("demonstrate a working knowledge of set theory by…").
- Mathematical notation is partly lost in the source corpus; 1–2 histories per course.
- The topic clusters are a balancing device only.

## D. What may and may not be claimed

May say: *In a preliminary evaluation (two same-course temporal hold-outs and one related-course transfer; three seeds; one 7B local model), the constraint-first pipeline produced validator-approvable, correctly formatted papers in 9 of 9 runs, whereas a one-shot LLM prompt produced none (0/9) and retrieval-only generation produced 2/9; the pipeline produced no near-copies of historical questions at any of five similarity levels. These results are descriptive; content quality was not human-evaluated, and the labelled Bloom data are too inconsistent to support a trained classifier.*

May not say: that the system outperforms LLMs in question quality; that it predicts exam content; that generated Bloom levels are verified; that topic coverage reflects the syllabus; anything about subjects/programmes outside this corpus.

## Reproduce

```powershell
.venv\Scripts\python.exe scripts\build_dataset.py
.venv\Scripts\python.exe scripts\audit_source_quality.py
.venv\Scripts\python.exe scripts\audit_labels.py
.venv\Scripts\python.exe scripts\audit_allocator.py
.venv\Scripts\python.exe scripts\audit_determinism.py ; .venv\Scripts\python.exe scripts\audit_determinism_state.py
.venv\Scripts\python.exe -u scripts\eval_generation.py all
.venv\Scripts\python.exe scripts\audit_leakage.py ; .venv\Scripts\python.exe scripts\audit_reproduce.py
```
