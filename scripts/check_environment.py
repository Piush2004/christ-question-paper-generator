"""Preflight check for the generation CLI (scripts/generate_paper.py): verifies required packages
import cleanly and the configured Ollama model is actually pulled and reachable, before any
generation run spends time only to fail with a confusing error partway through.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.ollama import OllamaClient  # noqa: E402

DEFAULT_PACKAGES = ["httpx", "pydantic", "numpy", "sentence_transformers", "ortools", "fpdf", "docx", "pymupdf"]


@dataclass
class EnvironmentReport:
    missing_packages: list[str] = field(default_factory=list)
    ollama_reachable: bool = False
    model_available: bool = False
    ok: bool = False
    messages: list[str] = field(default_factory=list)


def check_environment(client: OllamaClient | None = None, required_packages: list[str] = DEFAULT_PACKAGES) -> EnvironmentReport:
    client = client or OllamaClient()
    missing_packages: list[str] = []
    messages: list[str] = []
    for name in required_packages:
        try:
            importlib.import_module(name)
        except ImportError:
            missing_packages.append(name)
            messages.append(f"Missing package '{name}': run `pip install {name}` (or `pip install -r requirements.txt`).")

    model_available = client.is_available()
    ollama_reachable = model_available
    if not model_available:
        messages.append(
            f"Ollama is not reachable, or the model '{client.model}' is not pulled: "
            f"start Ollama and run `ollama pull {client.model}`."
        )

    ok = not missing_packages and model_available
    return EnvironmentReport(missing_packages, ollama_reachable, model_available, ok, messages)


if __name__ == "__main__":
    report = check_environment()
    if report.ok:
        print("OK — environment ready.")
    else:
        print("NOT READY:")
        for m in report.messages:
            print(f"  - {m}")
    sys.exit(0 if report.ok else 1)
