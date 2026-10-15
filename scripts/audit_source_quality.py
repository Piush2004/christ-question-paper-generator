"""Assign a source-quality status to every historical question (original text untouched).

Writes data/processed/source_quality.json  {question_id: {status, reasons, deterministic, llm_screen}}
and prints per-family counts. The LLM screen is resumable (cached in the same file)."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extraction import source_quality as sq  # noqa: E402
from src.generation import prompts  # noqa: E402
from src.llm.ollama import LLMOutputError, LLMUnavailableError, OllamaClient, wrap_untrusted  # noqa: E402

OUT = ROOT / "data" / "processed" / "source_quality.json"


def main(skip_llm: bool = False) -> None:
    Q = [json.loads(l) for l in (ROOT / "data" / "processed" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    P = {json.loads(l)["paper_id"]: json.loads(l) for l in (ROOT / "data" / "processed" / "papers.jsonl").read_text(encoding="utf-8").splitlines()}
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    client = OllamaClient(timeout_s=120)
    llm_ok = (not skip_llm) and client.is_available()
    for n, q in enumerate(Q):
        r = res.get(q["question_id"], {})
        det, why = sq.deterministic_status(q["text"], q["marks"])
        r.update({"deterministic": {"status": det, "reasons": why}})
        if llm_ok and "llm_screen" not in r:
            co = (q["course_outcomes"] or ["CO1"])[0]
            paper = P[q["paper_id"]]
            try:
                out = client.chat_json(prompts.CRITIC_SYSTEM, prompts.critic_user(
                    (paper["course_name"] or "").title(), paper["outcomes"].get(co, ""), q["marks"], q["text"]), temperature=0.0, max_tokens=150)
                r["llm_screen"] = {k: out.get(k) for k in ("answerable", "ambiguous", "needs_missing_data", "out_of_scope", "issue")}
            except (LLMOutputError, LLMUnavailableError):
                r["llm_screen"] = None
        st, reasons = sq.combine(det, why, r.get("llm_screen"))
        r.update({"status": st, "reasons": reasons})
        res[q["question_id"]] = r
        if n % 25 == 0:
            OUT.write_text(json.dumps(res, indent=1))
            print(f"  {n}/{len(Q)}", flush=True)
    OUT.write_text(json.dumps(res, indent=1))
    by_fam = defaultdict(Counter)
    for q in Q:
        by_fam[q["course_family"]][res[q["question_id"]]["status"]] += 1
    tot = Counter(r["status"] for r in res.values())
    print("TOTAL", dict(tot))
    for f, c in sorted(by_fam.items()):
        print(f"  {f:26s} n={sum(c.values()):3d} {dict(c)}")
    det_only = Counter(r["deterministic"]["status"] for r in res.values())
    print("deterministic only:", dict(det_only), "| llm screen run:", llm_ok)


if __name__ == "__main__":
    main(skip_llm="--skip-llm" in sys.argv)
