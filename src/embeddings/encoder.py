"""Sentence-embedding encoder (lazy singleton, GPU if available) used for topic clustering, novelty
scoring, retrieval and the Bloom classifier. Model name is configurable so experiments can compare
encoders; default is the encoder that won the measured comparison (see docs/EVALUATION_BLOOM.md)."""

from __future__ import annotations

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_cache: dict[str, object] = {}


def _model(name: str):
    if name not in _cache:
        import torch
        from sentence_transformers import SentenceTransformer
        _cache[name] = SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")
    return _cache[name]


def encode(texts: list[str], model_name: str = DEFAULT_MODEL) -> np.ndarray:
    if not texts:
        return np.zeros((0, 1), dtype=np.float32)
    return np.asarray(_model(model_name).encode(texts, batch_size=64, normalize_embeddings=True,
                                                show_progress_bar=False), dtype=np.float32)
