# Generation engine

Entry point: `python scripts/generate_paper.py --course <code|family> --session "November 2025" [--bloom 2:0.3,3:0.4,4:0.3] [--sections A:10x2,B:6x5:2,C:5x10:1]`

Every run writes a **new version** to `outputs/papers/<course>_<session>/v<N>/` (`paper.pdf`, `paper.docx`, `paper.json`); earlier versions are never overwritten. A paper is always a **draft** (footer says so) until a teacher approves it and it is exported with `--final`.

## Pipeline

```
history (older papers of the subject)
  -> topic clusters (KMeans over question embeddings; unsupervised, NOT official syllabus units)
  -> blueprint (sections, items, marks, OR-items, CO targets, RBT-share target)  .. validated first
  -> CP-SAT allocation: CO + RBT level + topic cluster for every slot           .. deterministic
  -> N LLM candidates per slot (JSON-schema validated, malformed output discarded)
  -> hard filters: not a near-copy of history, self-contained, length fits the marks, no in-paper duplicate
  -> ranking: verb-lexicon level fit, topic fit, CO fit, novelty, length fit
  -> moderator critic (LLM): answerable? ambiguous? needs missing figure/data? out of scope?
  -> deterministic validation of the whole paper -> PDF / DOCX / JSON with full provenance
```

### What is deterministic and what is a model

| Stage | Mechanism | Guarantee |
|---|---|---|
| Blueprint validation, allocation, paper validation | arithmetic / OR-tools CP-SAT, fixed seed | marks total, item counts, OR structure, every CO examined, topic cap — **hard**; RBT share and CO share — **soft, measured and reported** (marks are indivisible so exact shares are not always attainable) |
| Candidate text | local LLM (Ollama, default `qwen2.5:7b-instruct-q4_K_M`) | none — every candidate is filtered, ranked, criticised and shown to the teacher |
| RBT level check | verb lexicon (`src/bloom/lexicon.py`) | **measured best** of all tried level predictors on held-out subjects (docs/EVALUATION_BLOOM.md); the learned classifiers did not beat it, so they are off by default |

An impossible blueprint is rejected *before* any model call with reasons (e.g. "Sections add up to 90 marks but Max Marks is 100", "Level L1 target is smaller than half the smallest question"). Nothing is silently relaxed.

## Hard constraints, soft targets, and preferences (what each requirement is grounded in)

The historical corpus has **no verified Bloom, topic or unit labels** — only the paper setters' RBT/CO annotations, which the label audit (docs/EVALUATION_BLOOM.md) shows are noisy. The engine therefore distinguishes three strengths of requirement, and `paper.json` records which applies to every question (`constraint_provenance`):

| Kind | Meaning | Items |
|---|---|---|
| **HARD** | Supplied by the teacher/blueprint, enforced or the paper is refused | question count, section structure, marks per question, OR-pair structure, every course outcome examined at least once, originality (no near-copy of any past question), self-containedness |
| **SOFT target** | Optimised; deviation is *measured and reported*, not guaranteed | RBT mark-share (teacher-supplied target, tolerance ±max(2 marks, 5%); or, if none supplied, the course's historical marks→level pattern — i.e. a prior built from noisy labels), CO mark-share (teacher `co_weights` or historical share) |
| **PREFERENCE** | Steers generation; never a claim of truth | topic: an *unsupervised cluster* of past questions (not a syllabus topic), historical-frequency vs under-asked balance, recency penalty |

Consequences: a requested "L4" is a *requested target for the paper*, not evidence that historical L4 labels are reliable; a topic cluster is a retrieval/balancing device, not a verified curriculum unit. Only a teacher-specified CO, structure or marks scheme is a hard requirement. Every question is traceable to its slot, the constraint kind behind each attribute, the references shown to the model, and the model/prompt version.

When a course has a verified match in `data/processed/syllabus.json` (built by `scripts/build_syllabus.py` from the real CHRIST BCA syllabus documents), its topic provenance is reported as a **SOFT target** tied to a named syllabus unit instead of an unsupervised-cluster PREFERENCE. This is per-course: some courses — e.g. graph theory, per `scripts/build_syllabus.py`'s coverage report — have no syllabus match and keep the unsupervised-cluster path.

## Source-question status

Each historical question carries `VALID | EXTRACTION_ERROR | INCOMPLETE | NEEDS_HUMAN_REVIEW` (`src/extraction/source_quality.py`, `data/processed/source_quality.json`), with the deterministic and LLM-screen evidence stored separately. The original text is never changed or removed. Questions with deterministic defects (lost formula text, dangling "given below", unmapped glyphs) are excluded from exemplar/topic-cluster material; **all** questions, whatever their status, still take part in copy detection. The LLM screen can only raise `NEEDS_HUMAN_REVIEW`; `ILL_POSED`/`AMBIGUOUS` are reserved for human adjudication and are never assigned automatically.

## Format

All papers — PDF and DOCX — come from the single template in `src/generation/render.py`, which reproduces the layout of the institutional end-semester papers (header block, Course Code/Max Marks/Course Name/Duration, fixed General Instructions, Course Outcomes, per-section `marks*items=total` line, `N)` / marks / `(COk, Lj)` columns, centred **OR**, RBT legend). `tests/test_generation_format.py` re-parses every rendered PDF with the same parser that reads the real papers and requires it to recover the blueprint exactly — that test is what makes "same format for every paper" an enforced property rather than an intention. Only the university crest/watermark is not reproduced (institutional artwork).

## Provenance (`paper.json`)

Per question: section/number/part, text, marks, CO, RBT level, topic cluster, ranking scores, nearest historical question and its similarity, verb level, moderator verdict, number of candidates tried and why others were rejected, reference questions shown to the model, prompt version, model name, and `flagged_for_teacher` when every candidate failed a check and the least-bad one was kept.

## Safety / prompt-injection

Text from past papers reaches the LLM only inside `<<< … >>>` blocks labelled untrusted reference data, in the *user* turn; the system prompt is fixed and tells the model never to follow instructions found there. Every model reply is parsed as JSON and validated with Pydantic before use.

## Known limits (see docs/EVALUATION_GENERATION.md for measurements)

- No syllabus text is available: topics are clusters of past questions and the CO statements; questions about material that never appeared in past papers cannot be grounded.
- A 7B local model sometimes writes questions that are ambiguous or numerically unsound; the critic reduces but does not eliminate this. **Teacher review is mandatory.**
- Mathematical notation is lost in extraction of historical papers, so maths/graph-theory exemplars are partly garbled.
