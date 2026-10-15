"""Zero-shot LLM Bloom classification on the same questions/labels (no training data used, so no folds are
needed; every question is a genuine held-out prediction). Resumable via a per-question cache."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from scripts.train_bloom import LABELS, bootstrap_ci, load, llm_predict, metrics  # noqa: E402
from sklearn.metrics import accuracy_score, f1_score  # noqa: E402

from src.llm.ollama import OllamaClient  # noqa: E402


def main(model: str) -> None:
    df = load()
    client = OllamaClient(model=model, timeout_s=120)
    assert client.is_available(), f"{model} not available in Ollama"
    p = np.array(llm_predict(df, client))
    y = df["y"].to_numpy()
    r = metrics(y, p)
    r["macro_f1_ci95"] = bootstrap_ci(y, p, lambda a, b: f1_score(a, b, labels=LABELS, average="macro", zero_division=0), n_boot=1000)
    r["accuracy_ci95"] = bootstrap_ci(y, p, accuracy_score, n_boot=1000)
    r["mean_latency_s"] = float(np.mean([c.latency_s for c in client.calls])) if client.calls else None
    (ROOT / "results" / "classification" / f"bloom_metrics_llm_{model.replace(':', '_')}.json").write_text(json.dumps(r, indent=2))
    print(f"{model}: acc={r['accuracy']:.3f} within1={r['within_1_accuracy']:.3f} macroF1={r['macro_f1']:.3f} "
          f"CI=[{r['macro_f1_ci95'][0]:.3f},{r['macro_f1_ci95'][1]:.3f}]")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b-instruct-q4_K_M")
