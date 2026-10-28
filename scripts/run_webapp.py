"""Run the web app locally: python scripts/run_webapp.py [--port 5000] [--debug]

For live generation, Ollama must be running with the model pulled (same preflight as
scripts/generate_paper.py — run scripts/check_environment.py first). Without it, the app still
runs in showcase mode: every page works except the Generate form, which explains why.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.webapp.app import create_app  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    app = create_app()
    app.run(host=a.host, port=a.port, debug=a.debug, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
