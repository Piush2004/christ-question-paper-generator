# Dataset Contract

What this system expects when historical question papers are supplied, and what happens to them at
each stage. This is the interface contract between "papers you hand over" and "what the pipeline does
with them" — read this before dropping files into `data/raw/`.

## 1. Accepted formats

| Format | Support | Notes |
|---|---|---|
| `.pdf` (text-native) | Full | Extracted via PyMuPDF; page structure preserved. |
| `.pdf` (scanned/image-only) | Partial | Detected automatically (`needs_ocr` flag). OCR extraction is currently **blocked** — the Tesseract binary isn't installed on this machine yet (`docs/ENVIRONMENT_AUDIT.md` §3/§5). Such files are inventoried but not text-extracted until that's resolved. |
| `.pdf` (password-protected) | Rejected | No password source exists in this pipeline. Decrypt externally before placing in `data/raw/`. |
| `.docx` | Full | Extracted via python-docx. Page breaks are detected only from explicit page-break runs (no layout engine), so "page number" for DOCX is a best-effort logical count, not a rendered-page count. |
| `.txt` | Full | Read as UTF-8 with lossy fallback (`errors="replace"`) for any non-UTF-8 byte sequences — such replacements are not currently flagged, a known limitation (see `docs/PHASE_0_5_AUDIT.md`). |
| Anything else (`.jpg`, `.xlsx`, `.doc`, `.rtf`, ...) | Rejected | `UnsupportedFormatError` at load time; flagged invalid in the manifest, not silently skipped. |

## 2. Directory structure expected

Drop files anywhere under `data/raw/` (subdirectories are scanned recursively). No particular
subfolder structure is required or assumed — `scripts/prepare_data.py` finds every `.pdf`/`.docx`/
`.txt` file regardless of nesting.

```
data/raw/
├── <any structure you already have, e.g.>
│   ├── 2022/ML_endsem.pdf
│   ├── 2023/ML_endsem.pdf
│   └── DS_midsem_2023.docx
```

## 3. Filename / metadata expectations

**None, currently.** Academic year, program, semester, course, and subject are deliberately left
blank in the manifest rather than guessed from filenames — a wrong guess silently baked into every
downstream label would be worse than an honest blank (see `docs/RESEARCH_DECISION_LOG.md`,
"Dataset inventory / manifest builder"). If your filenames follow a consistent convention (e.g.
`<subject>_<year>_<examtype>.pdf`), tell us the convention and a parser can be added — it will not be
guessed silently.

## 4. What happens on ingestion (`scripts/prepare_data.py`)

1. Every file is validated (extension, size, PDF magic bytes) — failures are recorded per-file, never
   crash the whole scan.
2. Every valid file is content-hashed (SHA-256) and given a stable `document_id`.
3. Every valid file's text is extracted (page-by-page for PDF; best-effort logical pages for DOCX;
   whole-file for TXT).
4. Pages with too little extractable text are flagged `needs_ocr` — this does not block the rest of
   the document from being processed.
5. A manifest row is written for every file (valid or not) to `data/dataset_manifest.csv`.
6. A `dataset_version` id is computed from the content-hash of every file in the set and logged to
   `data/dataset_versions.json` (append-only, deduplicated — running the script again with the same
   files produces the identical version id, not a new entry).

## 5. OCR behavior

OCR is attempted only when a page's extractable text falls below a threshold (`MIN_TEXT_CHARS_PER_PAGE
= 20`, `configs/dataset.yaml`). It is currently **unavailable** on this machine (Tesseract binary not
installed) — scanned pages are flagged `OCR_REQUIRED`/`OCR_UNAVAILABLE` (see `src/ingestion/ocr.py`,
`OCRStatus`) rather than silently producing empty text. Text-native PDF/DOCX/TXT files are entirely
unaffected by this limitation.

## 6. Duplicate handling

Duplicate detection at this phase is **exact, document-level, content-hash based only**. If two files
have identical SHA-256 hashes (byte-identical content, even under different filenames), the manifest
marks the second occurrence's `duplicate_of` field with the first filename seen. This is NOT the same
as question-level near-duplicate detection (paraphrased repeats, same question reworded across years)
— that is the future novelty engine's job (`src/novelty/`, master-prompt §28) and requires a real
historical corpus with embeddings, not yet built.

## 7. Privacy considerations

Historical question papers are institutional material and are treated as potentially sensitive by
default:

- `data/raw/`, `data/interim/`, `data/processed/`, `data/annotations/`, `data/splits/`, and
  `data/evaluation/` are **gitignored** — their contents are never committed to version control, only
  the directory structure (`.gitkeep`) and the manifest (metadata only, no raw question text) are
  tracked.
- No file content is sent to any external service (LLM API, cloud OCR, etc.) at this phase — the
  pipeline is entirely local. Any future stage that does call an external API (LLM-assisted
  annotation, generation) will be documented explicitly before it's wired in, and should be reviewed
  for what content it actually transmits.

## 8. Processing lifecycle

```
data/raw/ (your files)
    -> validate_file()               per-file, controlled failure
    -> load_document()               PDF/DOCX/TXT -> DocumentText (pages preserved)
    -> build_manifest()               -> data/dataset_manifest.csv
    -> record_dataset_version()       -> data/dataset_versions.json
    -> QuestionExtractor().extract() -> ExtractedQuestion records (in-memory; not yet persisted
                                         to a canonical dataset file — that assembly step, plus
                                         the Question pydantic schema's document/dataset-level
                                         metadata fill-in, is the next piece of work once real
                                         files exist to test it against)
    -> compute_quality_metrics()      -> QualityMetrics
    -> run_quality_gate()             -> PASSED / FAILED (configs/quality_gate.yaml thresholds)
    -> assert_dataset_ready()         BLOCKS any further phase (annotation, training) on FAILED,
                                        unless --allow-unsafe-dataset is passed (loudly logged)
```

## 9. Dataset versioning

See `docs/RESEARCH_DECISION_LOG.md` ("Dataset versioning: content-hash based") for the design
rationale. In short: a dataset version id is a hash of exactly which files (by content, by validity)
were present — not an incrementing counter. Any future experiment that records which
`dataset_version` it used can be traced back to the exact file set, forever, without needing to keep
the manifest CSV itself pinned to that experiment.
