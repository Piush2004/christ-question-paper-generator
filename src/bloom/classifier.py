"""Production Bloom (RBT) classifier: sentence embedding (+ marks features) -> logistic regression.

The architecture/encoder used here is the one selected by the measured leave-one-subject-out
comparison in `scripts/train_bloom.py` (see docs/EVALUATION_BLOOM.md) — it is retrained on ALL labelled
questions for deployment, so its reported accuracy is the cross-validated figure, never a score on
its own training data.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from src.embeddings.encoder import encode

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "bloom_classifier.joblib"


def marks_features(marks) -> np.ndarray:
    m = np.asarray(marks, dtype=float)
    return np.stack([np.log1p(m), (m <= 3).astype(float), (m >= 8).astype(float)], axis=1)


class BloomClassifier:
    def __init__(self, encoder: str, use_marks: bool = True, C: float = 2.0):
        self.encoder, self.use_marks, self.C = encoder, use_marks, C
        self.clf: LogisticRegression | None = None
        self.classes_: list[int] = []

    def _x(self, texts: list[str], marks: list[float]) -> np.ndarray:
        e = encode(texts, self.encoder)
        return np.hstack([e, marks_features(marks)]) if self.use_marks else e

    def fit(self, texts: list[str], marks: list[float], y: list[int]) -> "BloomClassifier":
        self.clf = LogisticRegression(C=self.C, max_iter=4000, class_weight="balanced").fit(self._x(texts, marks), y)
        self.classes_ = [int(c) for c in self.clf.classes_]
        return self

    def predict_proba(self, texts: list[str], marks: list[float]) -> np.ndarray:
        """Always returns an (n, 6) array ordered L1..L6 (classes unseen in training get probability 0)."""
        p = self.clf.predict_proba(self._x(texts, marks))
        out = np.zeros((len(texts), 6))
        for j, c in enumerate(self.classes_):
            out[:, c - 1] = p[:, j]
        return out

    def predict(self, texts: list[str], marks: list[float]) -> list[int]:
        return [int(i) + 1 for i in self.predict_proba(texts, marks).argmax(axis=1)]

    def save(self, path: Path = MODEL_PATH, card: dict | None = None) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"encoder": self.encoder, "use_marks": self.use_marks, "C": self.C, "clf": self.clf,
                     "classes": self.classes_}, path)
        if card:
            path.with_suffix(".card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "BloomClassifier":
        d = joblib.load(path)
        o = cls(d["encoder"], d["use_marks"], d["C"])
        o.clf, o.classes_ = d["clf"], d["classes"]
        return o
