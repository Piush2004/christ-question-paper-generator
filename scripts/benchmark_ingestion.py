"""Performance baseline for ingestion + extraction (Phase 0.5 §18).

Measures wall-clock time and peak memory (via tracemalloc, stdlib — no new dependency) for
PDF/DOCX/TXT loading and question extraction over the fixture set. This is a BASELINE for future
comparison, not an optimization target — do not tune the pipeline against these numbers without a
concrete slowness complaint from real data (master-prompt §18: "do not optimize prematurely").

Usage:
    .venv/Scripts/python.exe scripts/benchmark_ingestion.py
"""

from __future__ import annotations

import sys
import time
import tracemalloc
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.extraction.engine import QuestionExtractor  # noqa: E402
from src.ingestion.loaders import load_document  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _time_and_memory(fn, *args, repeats: int = 20):
    tracemalloc.start()
    start = time.perf_counter()
    for _ in range(repeats):
        result = fn(*args)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed / repeats, peak


def main() -> None:
    print(f"Benchmarking against fixtures in {FIXTURES}\n")
    extractor = QuestionExtractor()

    txt_files = sorted(FIXTURES.glob("*.txt")) + sorted((FIXTURES / "adversarial").glob("*.txt"))
    print(f"{'file':45s} {'load(ms)':>10s} {'extract(ms)':>12s} {'peak_load_KB':>13s} {'peak_extract_KB':>16s}")
    for path in txt_files:
        doc, load_s, load_peak = _time_and_memory(load_document, path)
        _, extract_s, extract_peak = _time_and_memory(extractor.extract, doc)
        print(f"{path.name:45s} {load_s * 1000:10.3f} {extract_s * 1000:12.3f} "
              f"{load_peak / 1024:13.1f} {extract_peak / 1024:16.1f}")

    print()
    print("(txt loading dominates I/O time; PDF/DOCX have their own parser overhead not exercised")
    print(" here at meaningful scale until real multi-page historical papers arrive - re-run this")
    print(" benchmark once data/raw/ has real files, and compare against these numbers.)")


if __name__ == "__main__":
    main()
