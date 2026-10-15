"""Reproducibility test of the evaluation itself: regenerate one recorded paper (a) FRESH from the model with no
cache and (b) by REPLAY from the response cache, and compare question text with the recorded result."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from src.generation import baselines  # noqa: E402
from src.generation.blueprint import default_blueprint, load_papers, load_questions  # noqa: E402
from src.generation.pipeline import history_for  # noqa: E402
from src.llm.ollama import OllamaClient  # noqa: E402

RES = ROOT / "results" / "generation"


def regenerate(client, fam, held, seed):
    papers, questions = load_papers(), load_questions()
    code = next(p["course_code"] for p in papers if p["paper_id"] == held)
    profile = history_for(fam, papers, questions, exclude_paper_ids={held})
    bp = default_blueprint(code, "November 2025", papers=papers, questions=questions, before_session_of=held)
    bp.bloom_target = {2: 0.30, 3: 0.40, 4: 0.30}
    bp.seed = seed
    return [q.text for q in baselines.rag_slots(bp, profile, client, np.random.default_rng(seed))]


def main() -> None:
    ev = json.loads((RES / "generation_eval.json").read_text())
    rec = next(r for r in ev["results"] if r["system"] == "rag_slots" and r["family"] == "graph_theory" and r["seed"] == 7)
    recorded = [q["text"] for q in rec["questions"]]
    fresh = regenerate(OllamaClient(timeout_s=300), "graph_theory", rec["heldout_paper"], 7)
    replay_client = OllamaClient(cache_path=RES / "llm_cache.jsonl", replay_only=True)
    replay = regenerate(replay_client, "graph_theory", rec["heldout_paper"], 7)
    out = {"questions": len(recorded),
           "fresh_regeneration_identical_to_recorded": sum(a == b for a, b in zip(fresh, recorded)),
           "replay_identical_to_recorded": sum(a == b for a, b in zip(replay, recorded)),
           "replay_used_cache_for_all_calls": all(c.cached for c in replay_client.calls)}
    (ROOT / "results" / "audit" / "reproduce.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
