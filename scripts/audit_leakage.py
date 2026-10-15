"""Multi-level copy / leakage audit of generated questions.

For every generated question (all systems) compare against three corpora:
  history   — the older papers the system was allowed to see
  heldout   — the real paper that was held out (never visible to any system); similarity here is NOT a
              violation by itself, it shows whether outputs happen to resemble what was really asked
  other     — all other courses' questions (cross-subject copying)
at five levels: exact match; normalised match (case/punctuation/digits removed); word-3-gram Jaccard;
embedding cosine (MiniLM and mpnet); and a paraphrase cross-encoder (STS-B) on the top-3 embedding neighbours.
Also reports the same statistics for REAL held-out questions vs history, so the thresholds can be read against
how often real faculty re-ask questions."""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from src.embeddings.encoder import encode  # noqa: E402
from src.generation.generator import jaccard_3gram  # noqa: E402

CE_NAME = "cross-encoder/stsb-TinyBERT-L-4"


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z]+", " ", t.lower())).strip()


def cross_encoder():
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(CE_NAME, device="cuda")
    except Exception as exc:  # noqa: BLE001
        print(f"[cross-encoder unavailable: {type(exc).__name__}: {str(exc)[:80]}]")
        return None


def stats(texts, corpus_texts, corpus_emb, corpus_emb2, ce) -> dict:
    if not texts or not corpus_texts:
        return {}
    e1 = encode(texts)
    e2 = encode(texts, "sentence-transformers/all-mpnet-base-v2")
    s1, s2 = e1 @ corpus_emb.T, e2 @ corpus_emb2.T
    ntexts = [norm(c) for c in corpus_texts]
    rows = []
    for i, t in enumerate(texts):
        j = int(np.argmax(s1[i]))
        top = np.argsort(-s1[i])[:3]
        ce_score = float(max(ce.predict([(t, corpus_texts[k]) for k in top]))) if ce is not None else None
        rows.append({
            "exact": any(t.strip().lower() == c.strip().lower() for c in corpus_texts),
            "normalised": norm(t) in ntexts,
            "jaccard3": max(jaccard_3gram(t, c) for c in corpus_texts),
            "cos_minilm": float(s1[i, j]), "cos_mpnet": float(s2[i].max()), "paraphrase_ce": ce_score,
        })
    n = len(rows)
    f = lambda key, thr: float(np.mean([r[key] >= thr for r in rows if r[key] is not None])) if any(r[key] is not None for r in rows) else None  # noqa: E731
    return {
        "n": n, "exact": float(np.mean([r["exact"] for r in rows])), "normalised": float(np.mean([r["normalised"] for r in rows])),
        "jaccard3>=0.45": f("jaccard3", 0.45), "cos_minilm>=0.80": f("cos_minilm", 0.80), "cos_minilm>=0.88": f("cos_minilm", 0.88),
        "cos_mpnet>=0.80": f("cos_mpnet", 0.80), "paraphrase_ce>=0.80": f("paraphrase_ce", 0.80),
        "any_level_flagged": float(np.mean([r["exact"] or r["normalised"] or r["jaccard3"] >= 0.45 or r["cos_minilm"] >= 0.88 or r["cos_mpnet"] >= 0.88
                                            or (r["paraphrase_ce"] or 0) >= 0.80 for r in rows])),
        "mean_cos_minilm": float(np.mean([r["cos_minilm"] for r in rows])),
    }


def main() -> None:
    Q = [json.loads(l) for l in (ROOT / "data" / "processed" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    ev = json.loads((ROOT / "results" / "generation" / "generation_eval.json").read_text())
    ce = cross_encoder()
    cache: dict = {}

    def corpus(qs):
        key = tuple(q["question_id"] for q in qs)
        if key not in cache:
            tx = [q["text"] for q in qs]
            cache[key] = (tx, encode(tx), encode(tx, "sentence-transformers/all-mpnet-base-v2"))
        return cache[key]

    out = {"cross_encoder": CE_NAME if ce is not None else None, "by_system": {}, "real_heldout_vs_history": {}}
    seen_ref = set()
    for r in ev["results"]:
        fam, ho, hist_fam = r["family"], r["heldout_paper"], r.get("history_family", r["family"])
        hist = [q for q in Q if q["course_family"] == hist_fam and q["paper_id"] != ho]
        held = [q for q in Q if q["paper_id"] == ho]
        other = [q for q in Q if q["course_family"] != hist_fam and q["paper_id"] != ho]
        # a system may never have seen the held-out paper: assert it is absent from the history it could use
        assert not any(q["paper_id"] == ho for q in hist)
        texts = [q["text"] for q in r["questions"] if q["text"].strip()]
        entry = {}
        for name, qs in (("history", hist), ("heldout", held), ("other_courses", other)):
            tx, e1, e2 = corpus(qs)
            entry[name] = stats(texts, tx, e1, e2, ce)
        out["by_system"].setdefault(r["system"], []).append({"family": fam, "seed": r["seed"], **entry})
        if (fam, ho) not in seen_ref:
            seen_ref.add((fam, ho))
            tx, e1, e2 = corpus(hist)
            out["real_heldout_vs_history"][fam] = stats([q["text"] for q in held if q["n_words"] >= 4], tx, e1, e2, ce)
        print(f"{r['system']:15s} {fam:22s} seed {r['seed']}  vs history any-level flagged: {entry['history'].get('any_level_flagged', 0):.2f}  "
              f"cos>=0.88: {entry['history'].get('cos_minilm>=0.88', 0):.2f}  vs heldout cos>=0.80: {entry['heldout'].get('cos_minilm>=0.80', 0):.2f}", flush=True)
    d = ROOT / "results" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "leakage.json").write_text(json.dumps(out, indent=1))
    print("real held-out vs history:", json.dumps(out["real_heldout_vs_history"], indent=1)[:900])


if __name__ == "__main__":
    main()
