"""WSGI entrypoint for the web app (used by gunicorn in production: `gunicorn wsgi:app`).
Local development uses scripts/run_webapp.py instead, which runs Flask's dev server directly."""

from src.webapp.app import create_app

app = create_app()
