"""Label reliability audit (no second rater exists, so inter-annotator agreement is impossible; this uses the
only available repeated-measurement evidence).

Test-retest: the same (or near-identical) question appears in different papers of the same course, each time
labelled by the paper setter. If labels were reliable, repeats would carry the same RBT level. Reports pair
count, exact agreement, Cohen's kappa, mean |level difference|. Also: label entropy conditional on the
question's leading verb."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.metrics import cohen_kappa_score  # noqa: E402

from src.embeddings.encoder import encode  # noqa: E402
from src.generation.generator import jaccard_3gram  # noqa: E402


def main() -> None:
    Q = [json.loads(l) for l in (ROOT / "data" / "processed" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    Q = [q for q in Q if q["n_words"] >= 4]
    E = encode([q["text"] for q in Q])
    S = E @ E.T
    pairs = []
    for i in range(len(Q)):
        for j in range(i + 1, len(Q)):
            a, b = Q[i], Q[j]
            if a["paper_id"] == b["paper_id"] or a["course_family"] != b["course_family"]:
                continue
            if S[i, j] >= 0.90 or jaccard_3gram(a["text"], b["text"]) >= 0.6:
                pairs.append((a, b, float(S[i, j])))
    la = [int(a["rbt"][0][1]) for a, b, _ in pairs]
    lb = [int(b["rbt"][0][1]) for a, b, _ in pairs]
    out = {"n_same_course_repeat_pairs": len(pairs)}
    if pairs:
        out |= {
            "rbt_exact_agreement": float(np.mean([x == y for x, y in zip(la, lb)])),
            "rbt_within_1": float(np.mean([abs(x - y) <= 1 for x, y in zip(la, lb)])),
            "rbt_mean_abs_diff": float(np.mean([abs(x - y) for x, y in zip(la, lb)])),
            "rbt_cohen_kappa": float(cohen_kappa_score(la + lb, lb + la)) if len(set(la + lb)) > 1 else None,
            "co_exact_agreement": float(np.mean([a["course_outcomes"][0] == b["course_outcomes"][0] for a, b, _ in pairs])),
            "examples": [{"a": a["text"][:90], "b": b["text"][:90], "paper_a": a["paper_id"], "paper_b": b["paper_id"],
                          "rbt": [a["rbt"][0], b["rbt"][0]], "sim": round(s, 2)} for a, b, s in pairs[:12]],
        }
    # label entropy given leading verb
    verb = defaultdict(Counter)
    import re
    for q in Q:
        m = re.match(r"^\W*([A-Za-z]+)", q["text"])
        if m:
            verb[m.group(1).lower()][int(q["rbt"][0][1])] += 1
    ent = {}
    for v, c in verb.items():
        n = sum(c.values())
        if n >= 6:
            ent[v] = {"n": n, "entropy_bits": round(-sum(x / n * math.log2(x / n) for x in c.values()), 2),
                      "levels": dict(sorted(c.items()))}
    out["leading_verb_label_spread"] = dict(sorted(ent.items(), key=lambda kv: -kv[1]["n"]))
    tot = Counter(int(q["rbt"][0][1]) for q in Q)
    n = sum(tot.values())
    out["marginal_label_entropy_bits"] = round(-sum(x / n * math.log2(x / n) for x in tot.values()), 2)
    d = ROOT / "results" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "labels.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k not in ("examples", "leading_verb_label_spread")})
    for e in out.get("examples", [])[:8]:
        print(" ", e["rbt"], e["paper_a"], "|", e["a"][:70], "||", e["b"][:70])
    for v, r in list(ent.items())[:6]:
        print(" ", v, r)


if __name__ == "__main__":
    main()
