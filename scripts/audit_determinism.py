"""Why did the same seed give different outcomes? Measure LLM output determinism directly.

Same request (model, prompts, temperature, seed) sent repeatedly: (A) sequentially at the generation temperature,
(B) sequentially at temperature 0, (C) concurrently from several threads (what happens when two jobs share one
Ollama server, as happened in the first comparison run). Counts distinct responses. Must be run with the server
otherwise idle."""

from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.generation import prompts  # noqa: E402
from src.llm.ollama import OllamaClient  # noqa: E402

USER = prompts.generation_user("Operating System", "CO2", "Explain the importance of process and scheduling.", 2, 5,
                               ["scheduling", "process", "cpu"], "<<<reference questions\n- (5 marks, L2) Explain the states of a process.\n>>>")


def call(temp: float, seed: int, tag: str = "") -> str:
    c = OllamaClient(timeout_s=300)
    return json.dumps(c.chat_json(prompts.GENERATION_SYSTEM, USER + tag, temperature=temp, seed=seed, max_tokens=200), sort_keys=True)


def distinct(outs: list[str]) -> dict:
    c = Counter(outs)
    return {"calls": len(outs), "distinct_responses": len(c), "most_common_share": round(c.most_common(1)[0][1] / len(outs), 2)}


def main() -> None:
    res = {}
    res["A_sequential_temp0.85_same_seed"] = distinct([call(0.85, 123) for _ in range(8)])
    res["B_sequential_temp0_same_seed"] = distinct([call(0.0, 123) for _ in range(8)])
    with ThreadPoolExecutor(4) as ex:
        res["C_concurrent4_temp0.85_same_seed"] = distinct(list(ex.map(lambda _: call(0.85, 123), range(8))))
    with ThreadPoolExecutor(4) as ex:
        res["D_concurrent4_temp0_same_seed"] = distinct(list(ex.map(lambda _: call(0.0, 123), range(8))))
    d = ROOT / "results" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "determinism.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
