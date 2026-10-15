"""Protocol B: leave-one-PAPER-out Bloom evaluation with near-duplicate removal.

Complements the leave-one-subject-out protocol (scripts/train_bloom.py). Here the classifier may train on
other years' papers of the SAME subject (the realistic setting for a teacher who has past papers of their
own course), but any training question that is a near-duplicate of a test question (embedding cosine
>= 0.85 or word-3-gram Jaccard >= 0.5) is removed first, so a question that was simply re-asked in
another year cannot be 'memorised'.

Output: results/classification/bloom_metrics_leave_paper_out.json
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from scripts.train_bloom import (LABELS, SEED, bootstrap_ci, embed, fit_predict_emb, fit_predict_tfidf, load,  # noqa: E402
                                 metrics, short)
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.metrics import accuracy_score, f1_score  # noqa: E402

from src.bloom.lexicon import verb_level  # noqa: E402
from src.generation.generator import jaccard_3gram  # noqa: E402


def main() -> None:
    df = load()
    E = embed(df, "sentence-transformers/all-MiniLM-L6-v2")
    papers = sorted(df["paper_id"].unique())
    preds = {n: np.zeros(len(df), int) for n in ["majority", "verb_rule", "tfidf_lr", "MiniLM_lr", "MiniLM_lr+marks"]}
    removed_total = 0
    for pid in papers:
        te_i = np.where(df["paper_id"] == pid)[0]
        tr_i = np.where(df["paper_id"] != pid)[0]
        sims = E[tr_i] @ E[te_i].T
        keep = []
        for a, i in enumerate(tr_i):
            dup = (sims[a].max() >= 0.85) or any(jaccard_3gram(df["text"].iloc[i], df["text"].iloc[j]) >= 0.5
                                                 for j in te_i[np.argsort(-sims[a])[:3]])
            if not dup:
                keep.append(a)
        removed_total += len(tr_i) - len(keep)
        tr_i = tr_i[keep]
        tr, te = df.iloc[tr_i], df.iloc[te_i]
        preds["majority"][te_i] = DummyClassifier(strategy="most_frequent").fit(tr["text"], tr["y"]).predict(te["text"])
        preds["verb_rule"][te_i] = [verb_level(t) for t in te["text"]]
        preds["tfidf_lr"][te_i] = fit_predict_tfidf(tr, te)
        preds["MiniLM_lr"][te_i] = fit_predict_emb(E[tr_i], E[te_i], tr, te, False)
        preds["MiniLM_lr+marks"][te_i] = fit_predict_emb(E[tr_i], E[te_i], tr, te, True)
    y = df["y"].to_numpy()
    res = {n: metrics(y, p) for n, p in preds.items()}
    for n, p in preds.items():
        res[n]["macro_f1_ci95"] = bootstrap_ci(y, p, lambda a, b: f1_score(a, b, labels=LABELS, average="macro", zero_division=0), n_boot=500)
        res[n]["accuracy_ci95"] = bootstrap_ci(y, p, accuracy_score, n_boot=500)
    res["_meta"] = {"protocol": "leave-one-paper-out with near-duplicate removal", "papers": len(papers),
                    "train_questions_removed_as_near_duplicates_total": int(removed_total)}
    (ROOT / "results" / "classification" / "bloom_metrics_leave_paper_out.json").write_text(json.dumps(res, indent=2))
    print(f"papers={len(papers)} near-duplicate train removals (summed over folds)={removed_total}")
    print(f"{'model':18s} {'acc':>6s} {'within1':>8s} {'macroF1':>8s}  macroF1 95% CI")
    for n in preds:
        r = res[n]
        print(f"{n:18s} {r['accuracy']:6.3f} {r['within_1_accuracy']:8.3f} {r['macro_f1']:8.3f}  [{r['macro_f1_ci95'][0]:.3f}, {r['macro_f1_ci95'][1]:.3f}]")


if __name__ == "__main__":
    main()
