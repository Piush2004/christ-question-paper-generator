# Architecture — Evidence-Driven Component Decisions

This document maps every stage of the target pipeline to a technique category (deterministic
algorithm / classical ML / fine-tuned small model / retrieval / LLM) and states the evidence for that
choice. Per the operating rules, nothing here is fixed dogma — §56 (model selection) requires each
classification/ranking/retrieval choice to be benchmarked against alternatives once real data exists.
This is the **starting hypothesis**, not the final claim.

## Pipeline stage → technique mapping

| Stage | Technique category | Why |
|---|---|---|
| Document ingestion (PDF/DOCX/TXT parsing) | Deterministic | Structural parsing (PyMuPDF/pdfplumber/python-docx) is exact and auditable; no ambiguity to learn. |
| OCR fallback for scanned PDFs | Deterministic (Tesseract) | Off-the-shelf OCR; not a research contribution, a preprocessing necessity. Blocked pending Tesseract binary install (`ENVIRONMENT_AUDIT.md` §5). |
| Question/section/numbering detection | Deterministic (rule engine, regex + layout heuristics) | Numbering schemes (§10 of the master prompt) are a finite, enumerable grammar. A learned model would need labelled segmentation data we don't have yet, for a problem regex handles well. Revisit only if regex-based extraction's measured error rate (via `DATASET_ANALYSIS.md`) is too high on real scanned/malformed papers. |
| Marks extraction | Deterministic (regex over parenthetical/trailing patterns) | Same reasoning — finite pattern space. |
| Curriculum/syllabus mapping (unit/topic assignment) | Retrieval + embeddings, rules as fallback | No labelled unit/topic training data exists yet. Embedding similarity between question text and syllabus topic descriptions is a defensible zero-shot starting point; supersede with a trained classifier once gold labels exist and only if it measurably outperforms retrieval. |
| Bloom classification | Classical ML baseline (TF-IDF/embedding + linear classifier) vs. fine-tuned encoder vs. LLM zero/few-shot — **benchmarked, not assumed** | §22 explicitly requires comparing ≥2 approaches with real metrics before selecting. No default is declared here. |
| Webb DOK classification | Same as Bloom, independent evaluation | §23 explicitly forbids conflating Bloom and DOK. |
| Difficulty estimation | Structural features (concept count, marks, Bloom/DOK, question type) → classical regressor/classifier, with LLM-estimated difficulty as a comparison arm | No student-response data exists (`ENVIRONMENT_AUDIT.md`), so this is explicitly *estimated*, not psychometrically calibrated (§25). |
| Embeddings / semantic similarity | Fine-tuned/pretrained sentence embeddings (`sentence-transformers`) | Standard, well-evidenced choice for semantic similarity at this data scale; no case for training embeddings from scratch. |
| Novelty / duplicate detection | Deterministic (exact hash) + classical similarity (lexical n-gram, cosine on embeddings) — layered, not single-threshold | §28 explicitly forbids a single cosine-similarity cutoff. |
| Historical pattern / evolution analysis | Deterministic aggregation (pandas group-by over year/unit/Bloom/DOK/marks) | Pure statistics over annotated data; no model needed. Explicitly never framed as prediction (§27). |
| Assessment blueprint compilation | Deterministic allocation matrix from teacher-specified percentages | Direct arithmetic transform of constraints; no learning involved. |
| Constraint solver | Constraint programming (OR-Tools CP-SAT) | Hard constraints (marks/unit/count) plus soft objectives (balance/novelty) is a textbook CP-SAT / weighted-constraint-satisfaction shape, not an LP (objectives are not all linear-continuous) and not a evolutionary search (problem size at exam-paper scale, ~10-60 questions, is small enough for exact/near-exact solving — evolutionary methods are justified only if CP-SAT proves too slow at real problem sizes, to be measured). |
| Candidate question generation | LLM (provider-abstracted, §35) grounded by RAG context from curriculum + historical corpus | Generation from a structured, constrained prompt is exactly what current LLMs are evidenced to do well (`LITERATURE_BASELINE.md` §1E); no dataset exists to fine-tune a generator from scratch, and none should be attempted at this data scale (§3, §55). |
| Candidate ranking | Learned/heuristic multi-criteria scorer over quality/novelty/alignment sub-scores, benchmarked against a cross-encoder reranker | §56 requires the comparison; no default declared. |
| Answerability / adversarial validation | LLM-as-critic with structured rubric output, cross-checked by deterministic rule checks (e.g., marks-vs-expected-length) | No labelled adversarial-QA dataset for this domain exists; LLM critique with a validated rubric is the defensible starting point, subject to the same benchmarking discipline. |
| Psychometric simulation | Deterministic simulated-learner scoring (rule/probability model over difficulty × ability) — explicitly labelled `simulated`, never real IRT | §38/§39: real IRT (Rasch/2PL/3PL) requires real student response data this project does not have. |
| Retrieval (RAG) | Hybrid: faiss dense + sparse keyword filtering over curriculum/question-bank/historical corpus | Standard, evidenced choice; sparse+dense hybrid outperforms either alone at small corpus sizes typical of one institution's archive. |

## Why not "deep learning everywhere"

Per the master prompt's explicit instruction (§1, §3, §55, §66): the historical dataset has not yet
arrived, and until `DATASET_ANALYSIS.md` exists, no claim is made about its size. Pending that,
the hardware audit (`ENVIRONMENT_AUDIT.md`) already independently rules out training any generative
model from scratch: a single 8.5GB consumer GPU is enough to fine-tune small encoders, not to pretrain
a competitive generator. The default posture is therefore: deterministic algorithms wherever the
problem is a finite, enumerable grammar (parsing, extraction, blueprint math); classical ML as the
mandatory first baseline for every classification task; fine-tuning only where a classical baseline is
measurably beaten; retrieval instead of training wherever a knowledge lookup problem is being solved;
LLMs only for the tasks literature and current practice show them to be genuinely good at (open-ended
generation, rubric-based critique) and always behind a provider-agnostic interface (§35) with structured,
validated output (§36).

## Directory structure

See `README.md` for the realized directory tree (`src/`, `data/`, `configs/`, `docs/`, `tests/`, etc.)
— created to match master-prompt §7 exactly, populated incrementally as each stage is implemented.
