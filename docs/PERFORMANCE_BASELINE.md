# Performance Baseline

Phase 0.5 §18. Measured with `scripts/benchmark_ingestion.py` (stdlib `time.perf_counter` +
`tracemalloc`, no new dependency), 20 repeats per file, on the fixture set — the only data available
at this phase. **This is a baseline for future comparison, not an optimization target**: do not tune
the pipeline against these numbers without a concrete slowness complaint from real data.

## Current numbers (synthetic .txt fixtures, this dev machine)

| file | load (ms) | extract (ms) | peak load (KB) | peak extract (KB) |
|---|---|---|---|---|
| sample_sections.txt | 0.161 | 0.284 | 132.0 | 12.5 |
| sample_simple.txt | 0.205 | 0.091 | 131.1 | 4.3 |
| corruption_and_noise.txt | 0.163 | 0.241 | 130.7 | 6.1 |
| table_like.txt | 0.218 | 0.297 | 130.6 | 5.1 |

## What this does and doesn't tell us

- Sub-millisecond timings here are expected and uninteresting — these are few-line synthetic
  fixtures. The number worth tracking is **relative** cost (extraction vs. load) and **memory
  scaling**, not the absolute millisecond figures.
- PDF and DOCX parsing (PyMuPDF / python-docx) have real parser overhead this benchmark does not
  exercise at meaningful scale — fixtures are tiny. A real historical paper corpus (potentially
  scanned, multi-page, OCR-dependent) will look completely different. **Re-run this benchmark once
  real files exist in `data/raw/`** and compare against this baseline before drawing any conclusion
  about whether the pipeline is fast enough.
- The extraction engine is O(n) in document line count (two linear passes: classify, then span
  assignment) — no algorithmic red flags expected even at realistic exam-paper sizes (tens of pages).

## When to revisit

Only if real-data benchmarking shows the pipeline is actually too slow for the intended workflow
(e.g. minutes per paper at expected corpus size). Until then, this document exists to make "is it
fast enough" a measured question, not a guess.
