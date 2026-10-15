# Environment Audit

Date: 2026-08-18
Machine: local Windows 11 development workstation (single-node; no cluster/cloud compute yet provisioned).

## 1. Repository state at audit time

The working directory (`D:\Projects\Christ Question Paper model`) contained exactly one file:

```
Publication Part/Modern_Approaches_for_Automatic_Question_Paper_Generator.pdf
```

No existing source code, datasets, configs, tests, Docker, database, frontend, or backend. This is a
greenfield project. No prior work was overwritten or assumed; the audit below reflects what was built
from scratch during this session.

## 2. Hardware

| Component | Detail |
|---|---|
| CPU | AMD Ryzen 7 250 w/ Radeon 780M Graphics — 8 physical cores / 16 logical threads |
| RAM | 23.3 GB total |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU — **8.55 GB VRAM**, compute capability **12.0 (Blackwell / sm_120)** |
| Secondary GPU | AMD Radeon 780M (integrated) — 512 MB shared, not used for compute |
| Disk | D: drive — 270 GB free of 429 GB |
| Driver | NVIDIA driver 32.0.16.1088, CUDA UMD 13.3 (via `nvidia-smi`) |

**GPU smoke test** (`torch.cuda`, actual matrix multiplication executed, not just `is_available()`):

```
cuda available: True
device name: NVIDIA GeForce RTX 5060 Laptop GPU
capability: (12, 0)
matmul 4096x4096 x20 iterations: 0.56s
total VRAM: 8.55 GB
```

**Implication for the research plan:** sm_120 (Blackwell) is very new silicon. The default PyPI `torch`
wheel resolves to a `cu`-tag that does **not** ship sm_120 kernels — it must be installed from
`https://download.pytorch.org/whl/cu128` (confirmed working, see §4). 8.5 GB VRAM is enough to
**fine-tune** encoder models (BERT/DeBERTa-base or -large, small T5) with mixed precision and modest
batch sizes, and enough to run **inference** on 7–8B parameter LLMs quantized (int4/int8) if a local
LLM is ever wanted. It is **not** enough to train a generative language model from random
initialization at any scale that would be scientifically competitive — this hardware constraint
independently reinforces the "don't train an LLM from scratch" decision already dictated by dataset
size (see [`RESEARCH_GAP.md`](RESEARCH_GAP.md)).

## 3. Software

| Tool | Version |
|---|---|
| Python | 3.14.5 |
| pip | 26.1.1 → 26.2.1 |
| conda | not installed (not used; project uses stdlib `venv`) |
| Node.js | v24.16.0 |
| npm | 11.13.0 |
| Git | 2.54.0.windows.1 |
| Docker | present (Docker Desktop running, seen in GPU process list) — not yet used |

**Python 3.14.5 is a very recent release.** Before committing to it, every core ML dependency was
checked for an actual `cp314` wheel (not just a PyPI listing) by resolving and downloading:

| Package | Version resolved | cp314 wheel confirmed |
|---|---|---|
| torch | 2.11.0+cu128 (cu128 index) | yes |
| transformers | 5.15.0 | yes |
| sentence-transformers | 5.7.0 | yes |
| scikit-learn | 1.9.0 | yes |
| spacy | 3.8.13 (+ en_core_web_sm) | yes |
| pymupdf | 1.28.2 | yes |
| pdfplumber | 0.11.10 | yes |
| python-docx | 1.2.0 | yes |
| pytesseract | 0.3.13 | yes |
| faiss-cpu | 1.15.0 | yes |
| ortools | 9.15.6755 | yes |
| mlflow | 3.15.1 | yes |
| anthropic | 0.122.0 | yes |

All resolved and installed without conflict into a project-local virtual environment (`.venv/`,
created with stdlib `venv`, not conda — kept isolated from the global Python 3.14 install). One
version conflict was found and resolved: `mlflow<3.15.1` requires `pandas<3`, so `pandas` is pinned to
`>=2.2,<3` rather than the newly-released `pandas 3.0.3`. `pip check` reports no broken requirements
after installation. Full pinned list: [`requirements.txt`](../requirements.txt).

### Confirmed gap: OCR binary

`pytesseract` (the Python wrapper) is installed, but the underlying **Tesseract OCR binary is not
installed** on this machine (`where tesseract` found nothing). This blocks OCR extraction from
scanned/image-only PDFs until installed. Action required before scanned historical papers can be
processed: install Tesseract for Windows (UB-Mannheim build) and add it to `PATH`, or set
`pytesseract.pytesseract.tesseract_cmd` explicitly. The ingestion pipeline detects this and fails
loudly rather than silently skipping OCR (see `src/ingestion/ocr.py`).

## 4. What this rules in / rules out (evidence-based, per master-prompt §1)

- **Rules out**: training a transformer or any deep generative model from random initialization.
  Neither the dataset (not yet received, but historical-institutional-question-paper scale is
  presumptively small — hundreds to low thousands of questions, not the SQuAD-scale ~100k QA pairs
  the reference paper's transformer baselines were trained on) nor the hardware (single 8.5GB
  consumer GPU) support it. This must be re-validated numerically once §12/§13 (dataset analysis /
  quality gate) run on real data — this is a provisional, hardware-and-literature-grounded default,
  not yet a data-grounded one.
- **Rules in**: fine-tuning small pretrained encoders (Bloom/DOK/difficulty classifiers on top of
  sentence-transformer or DeBERTa embeddings), classical ML baselines (TF-IDF + logistic regression /
  SVM) as required first-pass baselines, dense + sparse retrieval (faiss + BM25-style) for RAG,
  constraint programming via OR-Tools CP-SAT for the blueprint solver (§31), and LLM APIs
  (Anthropic/OpenAI) or a locally-run quantized open model for the generation and adversarial-critic
  stages, behind a provider-agnostic abstraction (§35).
- **Undecided pending data**: whether a fine-tuned small transformer beats TF-IDF/embedding
  classical baselines for Bloom/DOK/difficulty is an empirical question for §22–§24, not assumed.

## 5. Outstanding environment actions

1. Install Tesseract OCR binary (blocks OCR path only; text-native PDF/DOCX/TXT ingestion is
   unaffected).
2. When real datasets arrive, re-run disk/RAM sizing — 270GB free is generous for a few hundred PDFs
   plus embedding indices, but should be re-checked if OCR image caches grow large.
3. No cluster/multi-GPU access exists. All training plans must fit an 8.5GB single-GPU budget.
