# Research Gap

Baseline for comparison: [`LITERATURE_BASELINE.md`](LITERATURE_BASELINE.md). This document states what
is genuinely new relative to that literature, and — equally importantly — what is **not** novel and
should never be described as such.

## 1. What is NOT novel (already established by the cited literature)

Do not claim credit for these in any later report:

- Using a transformer (T5/BERT/GPT-family) to generate a question from a passage — established by
  [23][24][25][26][27].
- Using RL with fluency/relevance/answerability rewards to steer generation — established by
  [19]-[22].
- Using retrieval/RAG-style context injection generally — implicit throughout the transformer section.
- Using IRT to condition generation on a target difficulty level — established by [28].
- The BLEU-4/METEOR/ROUGE-L metric trio for generation quality — standard throughout the field, and
  explicitly noted by the paper's own conclusion as an insufficient basis for judging real question
  quality (["using BLEU scores alone may not always be enough to capture the grammaticality and the
  relevance"], from the DoubAN discussion [18]).

If a future report reuses any of the above techniques (and several will be reused, e.g. transformer
fine-tuning for a classifier, RAG for retrieval), it must be described as **applying an established
technique to a new problem**, not as a contribution in itself.

## 2. Where the actual gap is

Cross-referencing §3 of `LITERATURE_BASELINE.md` (scope boundary) against the master-prompt's target
pipeline (`README.md` §"Target pipeline"), the gap clusters into four areas:

### Gap 1 — Unit of generation: a *paper*, not a *question*
Every reviewed system's unit of output is one question from one passage. None address the combinatorial,
constrained problem of assembling N questions into a paper that satisfies simultaneous hard constraints
(total marks, per-unit marks, question count, mandatory topics) and soft objectives (Bloom balance, DOK
balance, difficulty balance, novelty, historical compatibility) at once. This is the paper's stated
future-work direction in spirit ("context-aware question generation") but not addressed in substance.
**This project's constraint solver + multi-objective optimizer (blueprint compilation, CP-SAT-based) is
the direct response to this gap** — genuinely absent from the reviewed literature, not a re-badging of
an existing technique.

### Gap 2 — Curriculum-awareness
No reviewed system maps a question to a syllabus unit/topic/learning-outcome hierarchy, nor validates
generated content against out-of-syllabus concepts. SQuAD-style passage-grounded generation sidesteps
this because the passage *is* the context — there is no separate curriculum structure to be faithful to.
An institutional exam-paper generator cannot avoid this: a generated question must be checked against
what was actually taught. This motivates the curriculum representation graph and the syllabus-alignment
/ answerability / adversarial checks in this project's design — none of which have literature precedent
in the surveyed set.

### Gap 3 — Cognitive-level and difficulty modeling as first-class, independently evaluated tasks
The literature treats "difficulty" only as a generation *knob* (IRT-conditioned generation in [28]).
None of the reviewed work builds and *evaluates* an independent Bloom classifier or Webb DOK classifier
as a measured research artifact with its own accuracy/F1. This project's §22/§23 (Bloom and DOK models
built and evaluated as separate classification tasks, not folded into a generation reward) is a genuine
methodological gap-fill, contingent on the historical dataset containing (or being annotatable with)
enough labelled examples to make the evaluation meaningful — this claim must be re-validated against
real data quality (`DATASET_ANALYSIS.md`, not yet produced) before being asserted as achieved.

### Gap 4 — Historical grounding: novelty, repetition, and evolution against an institution's own past papers
The reviewed systems generate from a single passage with no notion of "has this been asked before, in
this form, at this institution." Novelty/duplicate detection against a historical exam archive, and
tracking how a concept's cognitive framing evolved across years, has no counterpart in the surveyed
work. This is the basis for the novelty engine (§28) and historical evolution analysis (§27) — explicitly
named "historical assessment evolution analysis" per this project's own naming convention, never
"prediction," since no evidence (here or in the literature) supports a predictive claim.

### Gap 5 (secondary) — Human/expert evaluation
The paper's own Table II shows only 2 of ~19 classified studies report expert/user assessment. This
project's mandatory human evaluation protocol (§50) and its refusal to report a metric without
measured evidence (§77 "most important research rule") is a direct, literature-supported response to
a gap the source paper itself identifies as under-explored — not an invented gap.

## 3. What must be measured, not assumed, before any of the above are claimed as achieved

Per the master prompt's overriding rule (never claim a result without evidence): every "genuine gap"
above is a design-time hypothesis about where this project's contribution lies. None of it is validated
yet, because there is no dataset yet. The obligations this creates:

1. Gap 1 (constraint solver) is validated by the solver actually returning feasible, constraint-respecting
   blueprints and by ablation (`Full - Blueprint Optimization`) showing degraded balance without it —
   not by existence of the code alone.
2. Gap 2 (curriculum-awareness) is validated by measured syllabus-alignment scores on real generated
   output, not by the presence of a curriculum graph data structure.
3. Gap 3 (Bloom/DOK models) is validated by reported accuracy/macro-F1 against a held-out gold set with
   inter-annotator agreement — and is void if the historical dataset turns out too small/imbalanced to
   support it (in which case §25/§55's small-dataset rule applies and this must be documented as a
   limitation, not silently dropped).
4. Gap 4 (novelty engine) is validated by measured precision/recall of duplicate detection against a
   hand-labelled sample of known-duplicate and known-novel question pairs.
5. Gap 5 (human evaluation) is validated only once real faculty ratings exist; until then, no claim of
   "faculty-acceptable" quality is permitted anywhere in this project's documentation.

This document will be revisited once the historical dataset arrives and `DATASET_ANALYSIS.md` /
`DATA_CARD.md` exist, to confirm or narrow these claims against actual data characteristics.
