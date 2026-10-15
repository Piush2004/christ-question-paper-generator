"""Is an LLM response a pure function of the request, or does it depend on server state (prompt/KV cache)?
Send request X, then X again, then a different request Y sharing the same system-prompt prefix, then X again, ...
Count how many distinct responses X receives."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.generation import prompts
from src.llm.ollama import OllamaClient

def req(tag, ex):
    return prompts.generation_user("Graph Theory", "CO2", "Apply the basics of graph theory.", 3, 8, ["tree", "spanning", "graph"],
                                   f"<<<reference questions\n- (8 marks, L3) {ex}\n>>>")
X = req("x", "Define a spanning tree. Find a spanning tree of the graph K4.")
Y = req("y", "Explain Kruskal's algorithm with an example and state its complexity in detail for a connected weighted graph.")
Z = req("z", "Describe Euler's theorem for planar graphs and verify it on the cube graph.")
c = OllamaClient(timeout_s=300)
def go(u): return json.dumps(c.chat_json(prompts.GENERATION_SYSTEM, u, temperature=0.85, seed=77, max_tokens=250), sort_keys=True)
seq = [("X", X), ("X", X), ("Y", Y), ("X", X), ("Z", Z), ("Z", Z), ("X", X), ("Y", Y), ("X", X)]
out = [(n, go(u)) for n, u in seq]
xs = [r for n, r in out if n == "X"]
res = {"X_calls": len(xs), "X_distinct_responses": len(set(xs)), "pattern": [("X", i) for i in range(len(xs))],
       "which_X_equal_first": [r == xs[0] for r in xs]}
(ROOT / "results" / "audit" / "determinism_state.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res))
