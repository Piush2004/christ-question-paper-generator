# Research Decision Log

Format per entry: Problem → Candidate solutions → Chosen solution → Reason → Evidence → Tradeoffs.
Failed/rejected experiments are kept, not deleted.

---

## 2026-08-18 — Runtime: Python 3.14.5 in a project-local venv, not conda

**Problem**: which Python environment manager to standardize on for a reproducible research
environment.

**Candidate solutions**: conda/mamba env; stdlib `venv`; no isolation (global site-packages).

**Chosen solution**: stdlib `venv` at `.venv/`.

**Reason**: conda is not installed on this machine (`ENVIRONMENT_AUDIT.md` §3) and installing it is an
unnecessary extra dependency when every required package (torch, transformers, faiss-cpu, ortools,
spacy, etc.) has confirmed pure-pip wheels for Python 3.14 on Windows.

**Evidence**: `pip download`/`pip index versions` confirmed cp314 wheels exist for every package in
`requirements.txt`; full `pip install -r requirements.txt` succeeded with `pip check` reporting no
broken requirements.

**Tradeoffs**: conda would have made a CUDA toolkit swap easier if the pip cu-tag wheel had not
matched the GPU; not needed here since cu128 wheels support sm_120 (Blackwell) correctly, confirmed
by an actual GPU matmul smoke test.

---

## 2026-08-18 — GPU: torch installed from the cu128 index, not default PyPI

**Problem**: default `pip install torch` did not certainly ship kernels for this GPU's compute
capability (12.0 / Blackwell, a very new architecture).

**Candidate solutions**: default PyPI `torch`; `--index-url https://download.pytorch.org/whl/cu128`;
CPU-only torch with GPU deferred to a later swap.

**Chosen solution**: `torch==2.11.0+cu128` from the cu128 index.

**Reason / Evidence**: installed and ran an actual CUDA matmul (4096×4096 ×20 iterations, 0.56s;
`torch.cuda.get_device_capability(0)` → `(12, 0)`), confirmed working. This is recorded explicitly so a
future `pip install -U torch` (which could silently resolve back to a non-cu128 build) is not done
without re-verifying the GPU smoke test.

**Tradeoffs**: none identified; this is the correct, verified choice for the current hardware.

---

## 2026-08-18 — Dependency conflict: pandas capped below 3.0

**Problem**: `pandas==3.0.3` (latest) conflicts with `mlflow==3.15.1`, which requires `pandas<3`.

**Candidate solutions**: downgrade mlflow to a version supporting pandas 3.x (none currently do);
drop mlflow; cap pandas.

**Chosen solution**: `pandas>=2.2,<3`.

**Reason**: mlflow is required for experiment tracking (§46) and no released version supports
pandas 3.x yet; pandas 2.x is fully capable for this project's tabular/dataframe needs.

**Evidence**: `pip install -r requirements.txt` `ResolutionImpossible` error explicitly named this
constraint; resolved cleanly after the pin, `pip check` clean.

**Tradeoffs**: revisit when mlflow adds pandas 3.x support — no functional loss identified at
pandas 2.3.3.

---

## 2026-08-18 — Deferred: OCR support blocked on missing system binary

**Problem**: `pytesseract` (Python wrapper) is installed, but the Tesseract OCR **binary** is not
present on this machine — a system-level install, not a pip package.

**Candidate solutions**: skip OCR support for now and fail loudly when a scanned PDF is encountered;
silently fall back to no-OCR text extraction (produces empty/garbage text for scanned pages); bundle
an alternative pure-Python OCR (e.g. `easyocr`, heavier GPU-based dependency).

**Chosen solution**: fail loudly (raise a clear, actionable error) when OCR is needed but the binary
is absent; do not silently degrade.

**Reason**: master-prompt Rule 4 ("never hide failures") and Rule 66 (no mocking of core pipeline
behavior) — a silent empty-text fallback would look like successful extraction and corrupt every
downstream stage without any visible signal.

**Evidence**: `where tesseract` confirmed absence; documented in `ENVIRONMENT_AUDIT.md` §3 as an
outstanding action item, not silently worked around.

**Tradeoffs**: scanned historical papers cannot be processed until Tesseract is installed by the user
(cannot be pip-installed; requires a separate Windows binary install). This is stated explicitly rather
than deferred silently.

---

## 2026-08-18 — Question/section segmentation: deterministic rules, not a learned segmenter

**Problem**: how to detect question boundaries, numbering, and marks across heterogeneous historical
paper formats (§10 of the master prompt: `Q1`/`1.`/`(a)`/Section A/Roman numerals/mixed).

**Candidate solutions**: hand-written regex/layout rule engine; sequence-labelling model (e.g.
token-classification transformer) trained to detect boundaries; LLM-based segmentation per page.

**Chosen solution**: deterministic rule engine (regex + light layout heuristics) as the first and
default implementation (`src/extraction/`).

**Reason**: the numbering grammar is finite and enumerable — this is not a case where "evidence-driven"
means "must use ML." A learned segmenter would need labelled boundary data that does not exist yet, to
solve a problem hand-written rules can solve deterministically and auditably (`ARCHITECTURE.md`).

**Evidence**: pending — to be validated against real historical papers once received; unit tests
(`tests/test_extraction.py`) currently cover synthetic fixtures spanning the numbering schemes named in
§10.

**Tradeoffs**: rule engines can fail silently on formats not anticipated. Mitigation: the engine reports
per-document extraction confidence/coverage (fraction of raw text matched into detected questions) so
low-confidence documents surface for review rather than silently producing incomplete data — this
is exactly what `data/dataset_manifest.csv` is for (§8).

---

---

## 2026-08-18 — Phase 0.5 hardening: provenance taxonomy expanded to a 6-state closed set

**Problem**: the original `LabelSource` enum (RULE/SYLLABUS_MATCH/EMBEDDING/LLM/HUMAN) didn't
distinguish "a human confirmed an existing prediction" from "a human typed this from scratch," and
didn't have a literal-content state for values that are stated verbatim rather than inferred.

**Chosen solution**: replaced with RAW / RULE_INFERRED / MODEL_PREDICTED / LLM_PREDICTED /
TEACHER_VERIFIED / MANUALLY_ENTERED, documented in `src/schemas/question.py`'s `LabelSource`
docstring. `Question.marks` was changed from a bare `float | None` to
`AnnotationProvenance[float]` — marks are usually RULE_INFERRED via regex and are exactly the kind
of field a teacher may need to correct, so losing that provenance would break §52 error analysis.

**Evidence**: `tests/test_schema.py` round-trips a full provenance chain through
`model_dump()`/`model_validate()` and confirms `is_reliable()` behavior for both the
low-confidence-until-verified and manually-entered cases.

**Tradeoffs**: none identified — this is additive; no existing code consumed the old enum values
(confirmed via `grep` before changing).

---

## 2026-08-18 — Dataset versioning: content-hash, not an incrementing counter

**Problem**: needed a way to answer "which exact set of papers was experiment X trained on" without
introducing mutable counter state that could drift between runs.

**Candidate solutions**: incrementing integer version bumped on every `prepare_data.py` run;
timestamp-based version; content-hash of the file set.

**Chosen solution**: `compute_dataset_version()` (`src/ingestion/dataset_version.py`) hashes the
sorted `(sha256, is_valid)` pairs of every scanned file. `data/dataset_versions.json` is an
append-only log, deduplicated by version id.

**Reason**: an incrementing counter would give a DIFFERENT version id on a second run over
unchanged files (violates idempotency, Phase 0.5 §9) unless carefully guarded; a content hash is
naturally idempotent — same files in, same id out, by construction, with no guard logic needed.

**Evidence**: `tests/test_dataset_version.py` — 5 tests proving idempotency (same files, same id,
across scan-order permutations), version change on file-set change, and append-only/deduplicated
log behavior.

**Tradeoffs**: a content-hash id is not human-orderable (you can't tell "v_a3f8e21c" is newer than
"v_b1029dfe" by looking at it) — `created_at` in the log entry carries that information instead.

---

## 2026-08-18 — Data-quality gate: named threshold checks, no composite score

**Problem**: master-prompt §13/§11 asks for a gate that blocks training on a failed dataset, with
configurable thresholds, but explicitly says "do not assign arbitrary scores yet."

**Chosen solution**: `run_quality_gate()` (`src/evaluation/data_quality/gate.py`) returns a list of
named `Issue`s (BLOCKING/WARNING/INFO), and overall status is FAILED iff any BLOCKING issue exists —
no weighted composite number anywhere.

**Reason**: a single "quality score" would need weights across incommensurable metrics (extraction
success rate vs. missing-subject rate vs. duplicate rate) that have no evidence-based justification
yet. Named checks are individually auditable and each threshold's rationale can be inspected/revised
independently in `configs/quality_gate.yaml`.

**Evidence**: `tests/test_data_quality_gate.py` — 8 tests including a full end-to-end run against
the real fixture set (not synthetic-only), proving the gate produces genuinely measured metrics, not
placeholders.

**Tradeoffs**: no single number to headline in a report; considered acceptable since the master
prompt explicitly discourages exactly that kind of premature scoring.

---

## 2026-08-18 — OCR: provider abstraction added ahead of a second implementation

**Problem**: master-prompt §10 (Phase 0.5) asked for a clean `OCRProvider`-style abstraction even
though Tesseract remains the only implementation.

**Chosen solution**: `OCRProvider` ABC with `is_available()`/`ocr_pdf_page()`; `TesseractOCRProvider`
is the sole implementation; `OCRStatus` enum (OCR_REQUIRED/OCR_UNAVAILABLE/OCR_COMPLETED/OCR_FAILED)
lets callers branch on outcome without exception-driven control flow for the expected-common cases.

**Reason**: this is a deliberate, requested exception to "don't build abstractions before a second
implementation exists" — the instruction explicitly asked for the boundary now, reasoning that a
future cloud-OCR swap is a known, likely direction (scanned historical papers are expected) and the
abstraction cost here is genuinely small (two methods).

**Evidence**: `tests/test_ocr.py` confirms the abstraction correctly reports OCR_UNAVAILABLE (the
true current state of this machine) rather than crashing or pretending success.

---

## 2026-08-18 — Regex bugs found and fixed by adversarial testing

Two genuine extraction bugs were found by Phase 0.5's adversarial fixture suite before any real
dataset existed:

1. **Bare `"1."` alone on its own line** (question number with no inline text, body starting next
   line) was not matched — `TOP_LEVEL_QUESTION` required `\s+` after the punctuation, which doesn't
   exist at end-of-line. Fixed: `[.)](?:\s+|$)`.
2. **Marks false-positive on code content** — `extract_marks()` matched `"(6)"` inside
   `"print(f(6))"` as if it were "6 marks," because a bare parenthesized number pattern doesn't
   distinguish a marks annotation from a function call. Fixed: added a negative lookbehind
   `(?<![A-Za-z0-9_])` so a bracket/paren immediately preceded by an identifier character is never
   read as marks.

**Evidence**: `tests/test_extraction_adversarial.py::test_dot_numbering` and
`::test_code_question_body_preserved` — both failed before the fix, both pass after, and are kept
in the suite as regression coverage.

**Tradeoffs**: the lookbehind fix is a heuristic (assumes marks are never glued directly to an
identifier), consistent with every documented marks format in the master prompt (§10) — none show
marks immediately following a letter/digit/underscore with no separator.

---

## 2026-08-18 — Manifest scan hardened against per-file crashes

**Problem**: `build_manifest()` called `load_document()` directly with no exception handling — one
corrupt or encrypted file anywhere in `data/raw/` would raise and abort scanning of every other file
in the directory, discovered by the Phase 0.5 adversarial ingestion tests
(`test_manifest_scan_survives_one_corrupt_file_among_valid_ones`, initially failing).

**Chosen solution**: `_manifest_row_for()` now wraps `load_document()` in a
`try/except (DocumentLoadError, UnsupportedFormatError)`, recording the failure as an
`is_valid=False` row with the specific error message, rather than propagating the exception.
`loaders.py` was also hardened to raise typed exceptions (`DocumentLoadError`,
`EncryptedDocumentError`, `UnsupportedFormatError`) instead of letting raw PyMuPDF/python-docx
exceptions escape uninterpreted.

**Evidence**: `tests/test_ingestion_adversarial.py` — corrupt PDF, corrupt DOCX, and
password-protected PDF all now degrade to a controlled per-file manifest entry; a corrupt file
sitting next to valid ones no longer prevents the valid ones from being scanned.

---

## 2026-10-05 — Real data arrived: dedicated layout-aware parser instead of the generic engine

**Problem**: the generic `QuestionExtractor` run on the 11 supplied papers produced 30–59 "questions" per paper where the papers have 13–27: it treated table cells, journal-entry numbers and trial-balance rows as question numbers, over-split sub-parts, and mislabelled OR-alternatives.

**Options**: keep patching regexes; learned segmenter; a parser that uses the (rigid) institutional layout.

**Decision**: `src/extraction/christ_parser.py` handles the two layouts actually present (terminator layout `N)` … `marks (CO, L)`; table layout `Q.No | Questions | CO | RBT`), requires sequential numbering, and **verifies every paper against itself** (items per section, marks per section, sum = Max Marks, CO+RBT on every question).

**Evidence**: all 11 supplied papers reconcile with 0 warnings (one "very short text" note for a formula-only question); `tests/test_christ_parser.py`. 34 older (2015–2022) data-bank files have no CO/RBT at all and are rejected, not guessed at.

**Tradeoffs**: tied to this institution's layouts; unknown layouts fail loudly (rejected with reason) rather than parse approximately.

---

## 2026-10-05 — Bloom classification: trained models did NOT beat a hand-written verb rule (negative result)

**Problem**: could a learned classifier predict the RBT level printed on each question?

**Tried**: TF-IDF+LR; three sentence encoders (MiniLM, bge-small, mpnet) + LR with/without marks; fine-tuned MiniLM; zero-shot Qwen2.5-7B; verb lexicon; majority. Leave-one-subject-out and leave-one-paper-out (near-duplicates removed).

**Result** (macro-F1, subject-held-out): majority 0.096; TF-IDF 0.178; MiniLM 0.180; fine-tuned MiniLM 0.161; verb rule 0.243; LLM zero-shot 0.275. See `docs/EVALUATION_BLOOM.md`.

**Decision**: deploy no learned Bloom classifier. Use the verb rule for ranking/validation; use zero-shot LLM only as an independent audit in experiments.

**Reason**: label audit shows the same verb carrying L1–L5 across papers (setter-specific conventions); 297 examples cannot learn that. Documented as a hypothesis, not proven.

**Tradeoff**: no calibrated confidence for levels; a teacher-verified, multi-rater label set is the prerequisite for revisiting this.

---

## 2026-10-05 — Generator v1 failure found by the held-out comparison: repeated themes via the fallback path

**Problem**: on graph theory, the full system produced four near-identical Huffman-coding questions (pairwise similarity 0.84–0.92). The per-candidate filter rejects within-paper similarity > 0.72, so these came through the *fallback* (all candidates filtered → keep the one least similar to history, ignoring the rest of the paper).

**Fix**: adaptive resampling (up to 3 rounds, telling the model which rejection reasons occurred), a "themes already used" list in the prompt, and a fallback that minimises similarity to history **and** to already-selected questions; fallback questions are flagged for the teacher.

**Evidence**: partial pre-fix results kept in `results/generation/generation_eval_v1_generator_partial.json`; post-fix results in `docs/EVALUATION_GENERATION.md`.

---

## 2026-10-05 — Prompt wording: "begin with an action verb" produced unnatural stems

**Problem**: the first generated OS paper had stems like "Apply the concept of file allocation to explain…" (verb-first instruction taken literally; label L3 but meaning L2).

**Fix**: prompt asks for a natural exam stem using a level-appropriate verb and forbids "Apply the concept of"; generic verbs removed from the suggestion list.

---

## 2026-10-05 — Validity audit: course families, hard/soft/preference constraints, reproducibility

**Problem**: an external review asked whether the generation claims were scientifically valid. Auditing found: (1) `course_family` merged Foundational vs Discrete Mathematics and PSD-I vs PSD-II (different courses, different COs) — two of three held-out "subjects" were not same-course experiments; (2) the generation experiment was called "subject-held-out" but is a temporal hold-out within a course; (3) the explanation "Ollama is not reproducible" was wrong — the earlier flip came from a prompt change; (4) the LLM judge scored real faculty questions below generated ones; (5) the validator-approval metric favours the system built to satisfy it.

**Decisions**: families = one course (enforced by `tests/test_no_leakage.py`); results re-run on 2 same-course targets + 1 explicitly labelled related-course transfer, 3 seeds; judge demoted to a diagnostic table; source questions get a status (VALID / EXTRACTION_ERROR / INCOMPLETE / NEEDS_HUMAN_REVIEW) with original text untouched and an LLM screen that can only request review; defective questions leave exemplar/cluster material but stay in copy detection; each generated question records which attributes are HARD, SOFT or PREFERENCE; responses cached for exact replay.

**Evidence**: `docs/VALIDITY_AUDIT.md`. Measured: identical back-to-back requests are deterministic, but the same request interleaved with others yielded 3 distinct responses in 5 calls (server prompt-cache state); fresh regeneration of a recorded run matched 8/25 questions, replay matched 25/25. Allocator: 48 random blueprints, 0 unsound solutions, 0 false rejections, 21/21 injected contradictions rejected. Label test-retest: 4/8 repeated questions kept the same RBT level (κ 0.29).

**Tradeoffs**: smaller evidence base after the family fix (histories of 1–2 papers); the LLM screen's 35% flag rate is uncalibrated, so no ill-posed count is claimed.

---

*(Log continues as further decisions are made — annotation strategy, split methodology, model
selection results, etc., once the historical dataset is received and Phases A–K of §73 begin.)*
