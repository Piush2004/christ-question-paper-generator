"""Generate a CHRIST-format question paper draft.

  python scripts/generate_paper.py --course BCA202-3 --session "November 2025"
  python scripts/generate_paper.py --course graph_theory --session "April 2026" --bloom 2:0.3,3:0.4,4:0.3
  python scripts/generate_paper.py --course BCA201-3 --session "April 2026" --sections A:10x2,B:6x5:2,C:5x10:1

--sections LABEL:ITEMSxMARKS[:CHOICE_ITEMS]   (omit to mirror the course's most recent paper)
--bloom    L:share,...  marks share per RBT level (omit to follow the course's historical pattern)

Output: outputs/papers/<course>_<session>/v<N>/paper.pdf|docx|json (a new version each run, never overwritten).
The result is always a DRAFT — a teacher must review and approve it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.generation import pipeline  # noqa: E402
from src.generation.blueprint import SectionSpec  # noqa: E402
from src.llm.ollama import LLMUnavailableError  # noqa: E402
from src.optimization.allocator import InfeasibleBlueprint  # noqa: E402


def parse_sections(s: str) -> list[SectionSpec]:
    out = []
    for part in s.split(","):
        bits = part.split(":")
        label = bits[0]
        n, m = bits[1].lower().split("x")
        out.append(SectionSpec(label, int(n), float(m), int(bits[2]) if len(bits) > 2 else 0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", required=True)
    ap.add_argument("--session", required=True, help='e.g. "November 2025"')
    ap.add_argument("--sections")
    ap.add_argument("--max-marks", type=int)
    ap.add_argument("--duration", type=int, help="minutes")
    ap.add_argument("--bloom")
    ap.add_argument("--history-weight", type=float)
    ap.add_argument("--candidates", type=int)
    ap.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--final", action="store_true", help="omit the DRAFT footer (only after teacher approval)")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()

    ov: dict = {}
    if a.sections:
        ov["sections"] = parse_sections(a.sections)
    if a.max_marks:
        ov["max_marks"] = a.max_marks
    if a.duration:
        ov["duration_minutes"] = a.duration
    if a.bloom:
        ov["bloom_target"] = {int(k.lstrip("Ll")): float(v) for k, v in (p.split(":") for p in a.bloom.split(","))}
    if a.history_weight is not None:
        ov["history_weight"] = a.history_weight
    if a.candidates:
        ov["candidates_per_slot"] = a.candidates
    if a.seed is not None:
        ov["seed"] = a.seed

    def prog(label, i, n):
        print(f"  [{i}/{n}] generating {label}", flush=True)

    try:
        res = pipeline.run(a.course, a.session, bp_overrides=ov, model=a.model, use_critic=not a.no_critic,
                           draft=not a.final, progress=prog)
    except InfeasibleBlueprint as e:
        print("\nCannot build this paper:")
        for p in e.problems:
            print("  -", p)
        return 2
    except LLMUnavailableError as e:
        print("\nLLM not available:", e)
        return 3
    v = res["validation"]
    print(f"\nVersion v{res['version']} written:")
    for k, f in res["files"].items():
        print(f"  {k}: {f}")
    print("Approvable (all hard checks pass):", v["approvable"])
    for c in v["checks"]:
        print(f"  [{'ok ' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    flagged = [i for i in res["paper"].items if i.fallback_used]
    if flagged:
        print("Flagged for teacher attention:", [f"Q{i.question.item}{i.question.part or ''}" for i in flagged])
    print("Timings (s):", {k: round(v, 1) for k, v in res["timings"].items()})
    return 0 if v["approvable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
