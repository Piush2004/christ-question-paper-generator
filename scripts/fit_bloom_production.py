"""Fit the deployable Bloom classifier on ALL labelled questions, using the encoder/feature setting that won
the leave-one-subject-out comparison (results/classification/bloom_metrics.json). Writes the model plus a
model card whose headline numbers are the cross-validated ones — never a score on training data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.bloom.classifier import BloomClassifier  # noqa: E402

ENCODERS = {"MiniLM": "sentence-transformers/all-MiniLM-L6-v2", "bge-small-en": "BAAI/bge-small-en-v1.5",
            "mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2"}


def main() -> None:
    metrics = json.loads((ROOT / "results" / "classification" / "bloom_metrics.json").read_text())
    cands = {k: v for k, v in metrics.items() if k.endswith(("_lr", "_lr+marks")) and not k.startswith("tfidf")}
    best = max(cands, key=lambda k: cands[k]["macro_f1"])
    enc_key = best.rsplit("_lr", 1)[0]
    use_marks = best.endswith("+marks")
    encoder = next(v for k, v in ENCODERS.items() if k.lower().replace("-", "") in enc_key.lower().replace("-", ""))
    rows = [json.loads(l) for l in (ROOT / "data" / "processed" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(rows)
    df = df[df["n_words"] >= 3]
    y = df["rbt"].map(lambda r: int(r[0][1])).tolist()
    clf = BloomClassifier(encoder, use_marks=use_marks).fit(df["text"].tolist(), df["marks"].tolist(), y)
    card = {
        "name": "bloom_classifier", "task": "6-way Revised Bloom's Taxonomy level of an exam question",
        "selected_config": best, "encoder": encoder, "uses_marks_feature": use_marks,
        "training_questions": int(len(df)), "training_papers": int(df["paper_id"].nunique()),
        "labels": "RBT level printed by the paper setter (human, noisy)",
        "cross_validated_performance": {k: cands[best][k] for k in ("accuracy", "within_1_accuracy", "macro_f1", "weighted_f1")},
        "validation_protocol": "leave-one-subject-family-out (see results/classification/bloom_report.md)",
        "limitations": ["only 297 questions, 8 subjects (BCA); L6 has <10 examples",
                        "labels are faculty judgements with visible inconsistency",
                        "performance on a new subject is the cross-validated figure above, not training accuracy"],
    }
    path = clf.save(card=card)
    print("selected:", best, "->", path)


if __name__ == "__main__":
    main()
