# Phase 0.5 Audit — Foundation Hardening Before Dataset Arrival

Date: 2026-08-18. Scope: adversarial audit and hardening of the Phase 0 foundation, performed before
any real historical question papers were supplied. No annotation, training, or generation work was
started — that remains correctly blocked (see "Exact next action," below).

## What was audited

Every file in the repository was re-read from disk (not recalled from memory of writing it) and
verified against its actual behavior, not its docstring claims:

- `README.md`, all of `docs/`, `configs/dataset.yaml`, `requirements.txt`
- `src/schemas/question.py` — the canonical record schema
- `src/ingestion/` — validation, loaders, OCR, manifest (all five files)
- `src/extraction/` — patterns, engine
- `scripts/prepare_data.py`
- The full test suite, run fresh, before any changes were made

Baseline before this pass: 16 tests, all passing, no warnings. That was confirmed genuinely true
(not assumed from the prior session's report) before any hardening work began.

## Bugs found

All found via adversarial testing written *before* the fix (test-first), not invented after the fact:

1. **Bare `"1."` numbering not matched** — a question number alone on its own line with the question
   body starting on the next line (`"1.\nWhat is precision?\n"`) was silently dropped, because
   `TOP_LEVEL_QUESTION` required trailing whitespace after the punctuation, which doesn't exist at
   end-of-line. Real institutional papers plausibly use this layout (numbers on their own line is a
   very common PDF/OCR artifact). Fixed in `src/extraction/patterns.py`.
2. **Marks false-positive on embedded code/expressions** — `extract_marks()` read `"(6)"` inside
   `"print(f(6))"` as "6 marks" because a bare parenthesized number pattern can't distinguish a marks
   annotation from a function call or array index. This would have silently corrupted marks
   extraction on any programming-question paper. Fixed with a negative lookbehind requiring the
   bracket/paren not be glued to an identifier character.
3. **Manifest scan crashed on one bad file among many good ones** — `build_manifest()` called
   `load_document()` with no exception handling; a single corrupt or password-protected PDF anywhere
   in `data/raw/` would raise and abort the entire directory scan, silently losing every other valid
   file's inventory data for that run. This is the most serious bug found — it would have meant one
   bad file in a real historical-paper drop makes `scripts/prepare_data.py` fail with no manifest
   output at all, no indication of which file was the problem. Fixed: `loaders.py` now raises typed,
   specific exceptions (`DocumentLoadError`, `EncryptedDocumentError`, `UnsupportedFormatError`)
   instead of letting raw PyMuPDF/python-docx exceptions escape; `manifest.py` catches them per-file
   and records a controlled `is_valid=False` row with the actual error message.
4. **`Question.marks` field type mismatch caught by mypy** — was `str | None`... no, was a bare
   `float | None` with no provenance despite being a value that's frequently rule-inferred and
   sometimes teacher-corrected; and separately, `ManifestRow.source` was typed `str | None` when
   every code path actually always sets it to a real string — mypy caught this as a real type error
   in `scripts/run_quality_gate.py` (`Path(row.source)` with `row.source: str | None`). Both fixed.
5. **Pydantic and PyMuPDF deprecation warnings** — `class Config:` (deprecated since pydantic 2.0,
   removal planned for 3.0) replaced with `model_config = ConfigDict(...)`; `import fitz` replaced
   with `import pymupdf as fitz` per PyMuPDF's own deprecation notice. Neither was failing, but both
   were live warnings that would become hard failures on a future dependency bump.
6. **Console output mangled on Windows** — several user-facing print strings used em-dashes (`—`),
   which render as `�` under the default Windows console codepage (confirmed by actually running the
   CLI and reading the mangled output, not assumed). Replaced with plain hyphens in every printed
   (not docstring) string.

None of these were weakened tests to make them pass — every fix changed production code; every test
that initially failed now passes for the right reason, verified by re-running.

## New tests

56 new tests added (16 → 72), across:

| File | Count | Covers |
|---|---|---|
| `test_extraction_adversarial.py` | 19 | Every numbering/section/marks/corruption/table/math/code/length/empty case listed in the hardening brief |
| `test_ingestion_adversarial.py` | 7 | Corrupt PDF/DOCX, encrypted PDF, unsupported extension, blank PDF, manifest survival under bad files |
| `test_ocr.py` | 5 | OCR status reporting, confirmed-unavailable state, no-crash on OCR attempt |
| `test_schema.py` | 4 | Full provenance round-trip, reliability semantics, source-taxonomy distinctness |
| `test_dataset_version.py` | 5 | Idempotency (identical files → identical version, twice), version change on file-set change, append-only/deduplicated log |
| `test_data_quality_gate.py` | 8 | Empty-dataset failure, real-fixture-set end-to-end metrics, training-blocker raise/override/passthrough |
| `test_future_component_interfaces.py` | 7 | Every not-yet-implemented ML interface raises rather than fabricates |
| `test_extraction.py` (+1) | 1 | Line-level source provenance reconstructs exactly from raw text |

Every test in this list was run and confirmed passing as part of this audit — the counts above are
measured, not estimated (`pytest tests/ -q` → `72 passed`).

## What was hardened (beyond bug fixes)

- **Provenance taxonomy**: `LabelSource` expanded to the requested 6-state closed set
  (RAW / RULE_INFERRED / MODEL_PREDICTED / LLM_PREDICTED / TEACHER_VERIFIED / MANUALLY_ENTERED);
  `Question.marks` is now provenance-wrapped; `source_line_start`/`source_line_end` added to both
  the schema and the extraction engine, and a test proves the exact source line range reconstructs
  the original raw text byte-for-byte.
- **OCR abstraction**: `OCRProvider` ABC + `TesseractOCRProvider` + `OCRStatus` enum
  (OCR_REQUIRED/OCR_UNAVAILABLE/OCR_COMPLETED/OCR_FAILED). Tesseract was **not** installed as part of
  this pass, per the explicit instruction not to add it just to silence a warning — its absence is
  now reported as a clean, typed status instead of an ad-hoc warning string.
- **Dataset versioning**: content-hash based (`src/ingestion/dataset_version.py`), inherently
  idempotent by construction rather than by a rerun-detection guard; `data/dataset_versions.json` is
  an append-only, deduplicated log.
- **Data-quality gate**: `src/evaluation/data_quality/` computes real metrics from real manifest +
  extraction output (no fabricated numbers — verified by the end-to-end fixture test), applies
  configurable thresholds (`configs/quality_gate.yaml`), and produces BLOCKING/WARNING/INFO issues
  with no composite score. `assert_dataset_ready()` is the training blocker: raises
  `DatasetNotReadyError` on a failed gate unless `--allow-unsafe-dataset` is passed, which always
  prints a loud, unmissable warning naming the bypassed issues.
- **Fixture-vs-real data policy**: `Origin` (manifest) / `DataOrigin` (schema) enums
  (real/fixture/synthetic/evaluation); every test now explicitly tags its data as `FIXTURE`; the
  real-data entry point (`scripts/prepare_data.py`) always tags `data/raw/` scans as `REAL`.
  Mechanically enforced, not just documented — every `build_manifest()` call site was audited and
  fixed to pass the correct origin.
- **Interfaces for future ML components**: `BloomClassifier`, `DOKClassifier`,
  `DifficultyEstimator`, `QuestionGenerator`, `NoveltyScorer`, `PaperOptimizer` — each a minimal ABC
  whose not-yet-implemented default raises `ComponentNotYetAvailableError` with a specific reason,
  never a fabricated value. Verified by test (`test_future_component_interfaces.py`).
- **Config audit**: grepped the entire repo for absolute paths, API keys, secrets, hardcoded
  credentials — none found. All paths in `configs/*.yaml` are relative; the only machine-specific
  fact recorded anywhere is the documented GPU/CUDA index requirement in `requirements.txt`'s header
  comment, which is inherent to the hardware, not a leaked secret.
- **Lint/type tooling**: ruff and mypy added (justified by this phase's explicit code-quality-audit
  request; not a large toolchain — two focused, fast tools). All findings fixed: 8 enum
  modernizations (`str, Enum` → `StrEnum`, Python 3.14-idiomatic), unused imports, import ordering,
  one `assert False` anti-pattern, one real type error (see bug #4 above). `ruff check` and
  `mypy src/ scripts/ tests/` are both clean.
- **Performance baseline**: `scripts/benchmark_ingestion.py` (stdlib `time`/`tracemalloc`, no new
  dependency) measures load + extraction time and peak memory; results in
  `docs/PERFORMANCE_BASELINE.md`. Explicitly framed as a baseline for comparison once real data
  exists, not an optimization target — synthetic fixtures are too small to draw conclusions from
  directly.
- **Reproducibility**: actually verified, not assumed — a throwaway venv (`.venv_repro_check`,
  deleted after the check) was created fresh, `pip install -r requirements.txt` ran clean, `pip
  check` reported no broken requirements, and all 72 tests passed. This confirms the README's
  "Getting started" steps work from a genuinely clean environment state, not just the
  already-warmed development venv.
- **Dataset contract**: `docs/DATASET_CONTRACT.md` — formal statement of accepted formats, directory
  expectations, OCR/duplicate/privacy behavior, and the exact processing lifecycle a dropped file
  goes through.
- **Dataset analysis framework**: `docs/DATASET_ANALYSIS.md` — every section explicitly marked
  PENDING rather than filled with placeholder numbers; states exactly what will populate it and by
  what code, once real data exists.

## Remaining limitations (known, documented, not silently hidden)

1. **OCR is still unavailable.** Tesseract was not installed, per explicit instruction. Scanned
   pages are correctly detected and reported (`OCRStatus.OCR_UNAVAILABLE`), not silently skipped.
2. **Table-formatted mark columns are not correctly parsed** — verified by
   `test_table_like_layout_does_not_crash`: numbering in a table's leading column is still detected,
   but a marks value sitting in a separate whitespace-padded column (with no unit suffix) is
   correctly *not* picked up, to avoid false-positive matches on arbitrary numbers. A dedicated
   table-aware extractor is out of scope for the current rule-based line engine.
3. **Bare alphabetic sub-questions without any parentheses** (e.g. `"a. Explain..."` with no `(` or
   `)` at all) are not matched by `SUB_QUESTION_ALPHA` — every documented format in the master
   prompt uses parentheses, so this was not fixed, only noted, pending confirmation this format
   actually appears in real papers.
4. **Non-UTF-8 `.txt` files are lossily decoded** (`errors="replace"`) without currently flagging
   that replacement characters were substituted — documented in `docs/DATASET_CONTRACT.md` §1 as a
   known gap, not fixed this pass.
5. **DOCX page counting is best-effort logical**, based only on explicit page-break runs in the
   XML — python-docx has no layout engine, so this will not match a rendered page count for a
   real-world DOCX without manual page breaks.
6. **No canonical-dataset assembly step yet.** `ExtractedQuestion` (extraction engine's dataclass)
   and `Question` (pydantic schema) are currently separate — there is no glue function that takes
   manifest + extraction output and produces populated `Question` records with `dataset_version`,
   document-level metadata, etc. filled in. This is deliberately deferred: building it now, with no
   real data to validate the mapping against, risks guessing wrong about what fields matter. It is
   the first piece of work once real papers arrive.
7. **Performance baseline is synthetic-fixture-only** — real PDF/DOCX parsing performance at the
   scale of actual multi-page historical papers is unverified. Explicitly flagged in
   `docs/PERFORMANCE_BASELINE.md` as something to re-measure once real files exist.
8. **No filename-to-metadata parser** — academic year/subject/course/program remain blank in every
   manifest row until a real naming convention is confirmed with the source institution (unchanged
   from Phase 0; still the correct choice per Rule 4).

## Dataset readiness

**NOT READY — no dataset has been received.** The pipeline that will receive it is verified ready:
`scripts/prepare_data.py` and `scripts/run_quality_gate.py` both run cleanly against an empty
`data/raw/` (exit 1, correctly reporting `no_documents` as the blocking issue — verified by direct
execution, not assumed) and against the fixture set (exit 0, `PASSED`, with correctly-surfaced
warnings about missing subject/year metadata).

## OCR readiness

**NOT READY.** Tesseract binary absent (confirmed via `shutil.which`, both directly and through
`TesseractOCRProvider.is_available()` — test asserts this is `False` on this machine, so a future
Tesseract install will be caught by a failing test, prompting an intentional update rather than a
silent behavior change). Install path documented in `docs/ENVIRONMENT_AUDIT.md` §3/§5 and
`docs/DATASET_CONTRACT.md` §5; not performed, per instruction.

## Reproducibility

**VERIFIED**, not assumed — see "What was hardened" above. Fresh venv, clean `pip install`, clean
`pip check`, all 72 tests pass.

## Performance baseline

Established (`docs/PERFORMANCE_BASELINE.md`), synthetic-fixture-only, explicitly framed as a
comparison point rather than a target. Sub-millisecond timings on tiny fixtures; extraction engine is
O(n) in line count with no algorithmic concerns at expected real-paper scale (tens of pages).

## Security concerns

- No secrets, API keys, or credentials found anywhere in the repository (grepped explicitly).
- No hardcoded absolute or machine-specific paths in source/config (grepped explicitly; only
  documentation of the GPU/CUDA index requirement, which is inherent to the hardware).
- `data/raw/`, `interim/`, `processed/`, `annotations/`, `splits/`, `evaluation/` are gitignored —
  institutional paper content is never committed, only directory structure and the manifest (which
  contains filenames/hashes/metadata, not question text).
- No external network calls happen anywhere in the current pipeline (ingestion, extraction, quality
  gate are all local). The only network-capable dependencies installed (`anthropic`, `openai`,
  `langchain-core`) are unused by any code that runs today — they are Phase-3+ generation
  dependencies staged early per the environment audit, not yet wired to anything.

## Architecture changes

All additive; no redesign of the core ingestion/extraction pipeline. Summary: provenance taxonomy
expanded (schema), OCR abstracted behind a provider interface (ingestion), dataset versioning added
(ingestion), a full data-quality gate module added (new `src/evaluation/` package), six clean
not-yet-implemented ML interfaces added (six new near-empty `src/*/interface.py` files), lint/type
tooling added (dev-only). `docs/ARCHITECTURE.md`'s technique-selection table and reasoning are
unchanged — nothing in this pass contradicted or required revising that document.

## Exact next action when the dataset arrives

1. Drop `.pdf`/`.docx`/`.txt` files into `data/raw/` (any subdirectory structure; see
   `docs/DATASET_CONTRACT.md`).
2. Run `scripts/prepare_data.py` — inventory, hash, per-file OCR-need detection, dataset version.
3. Run `scripts/run_quality_gate.py` — real metrics (extraction success rate, question count, marks/
   section extraction rate, missing-metadata rates, duplicate rate) against
   `configs/quality_gate.yaml` thresholds.
4. **If the gate reports FAILED**: stop. Read the BLOCKING issues, fix what's fixable (e.g. if
   extraction success rate is low, that likely means the extraction engine needs new patterns for a
   format not yet seen — extend `src/extraction/patterns.py` the same way this audit did, test-first
   against a new adversarial fixture built from the actual failing real-paper text, not a synthetic
   guess).
5. **If the gate reports PASSED** (warnings are expected and fine, e.g. missing subject/year until a
   naming convention is confirmed): populate `docs/DATASET_ANALYSIS.md` with real numbers (a
   `scripts/generate_dataset_analysis.py` needs to be written to render `QualityMetrics` into that
   document's tables and `results/figures/` plots — not yet built, first task of that phase).
6. Only then does master-prompt §73 Phase D (annotation) begin — building the annotation pipeline
   (rules → syllabus matching → embeddings → LLM-assisted labeling → confidence scores → human
   verification, §14) was explicitly out of scope for this hardening pass and remains unbuilt.

## Final state

```
FOUNDATION READY
DATASET NOT YET RECEIVED
TRAINING BLOCKED BY DESIGN (assert_dataset_ready() raises without a real dataset; the CLI exits 1)
```

72/72 tests passing. `ruff check` clean. `mypy` clean. No fabricated metrics, no fabricated dataset,
no model claimed trained.
