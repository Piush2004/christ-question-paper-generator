"""Flask app factory wiring the web UI to the existing generation pipeline (src/generation/pipeline.py)
unchanged — the web layer is a thin consumer, the same way scripts/generate_paper.py is. Generation
runs on a background thread via JobManager so no request ever blocks on an LLM call; the client polls
/api/jobs/<id> for progress. check_environment() (same preflight the CLI uses) decides whether the
Generate form can run live or must show a showcase-mode notice instead of silently failing."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for

from scripts.check_environment import EnvironmentReport, check_environment
from src.generation import pipeline
from src.webapp.catalog import list_courses, list_generated_papers
from src.webapp.forms import build_overrides
from src.webapp.jobs import JobManager

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAPERS_JSONL = ROOT / "data" / "processed" / "papers.jsonl"
DEFAULT_OUT_ROOT = ROOT / "outputs" / "papers"
ALLOWED_DOWNLOAD_NAMES = {"paper.pdf", "paper.docx", "paper.json"}
ENV_CACHE_TTL_S = 15.0


def create_app(
    *,
    run_fn: Callable[..., dict] = pipeline.run,
    environment_check_fn: Callable[[], EnvironmentReport] = check_environment,
    papers_jsonl: Path = DEFAULT_PAPERS_JSONL,
    out_root: Path = DEFAULT_OUT_ROOT,
) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "christ-question-paper-intelligence-local-demo"
    jobs = JobManager(run_fn=run_fn)
    out_root = Path(out_root)
    env_cache: dict = {"report": None, "checked_at": 0.0}

    def cached_environment_report() -> EnvironmentReport:
        now = time.time()
        if env_cache["report"] is None or now - env_cache["checked_at"] > ENV_CACHE_TTL_S:
            env_cache["report"] = environment_check_fn()
            env_cache["checked_at"] = now
        return env_cache["report"]

    @app.template_filter("datetimeformat")
    def datetimeformat(epoch_seconds: int) -> str:
        return datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%d %H:%M")

    @app.context_processor
    def inject_globals() -> dict:
        return {"env_status": cached_environment_report}

    @app.route("/")
    def home():
        courses = list_courses(papers_jsonl)
        recent_papers = list_generated_papers(out_root)[:5]
        return render_template("home.html", courses=courses, recent_papers=recent_papers, active="home")

    @app.route("/generate", methods=["GET", "POST"])
    def generate():
        courses = list_courses(papers_jsonl)
        if request.method == "GET":
            return render_template("generate.html", courses=courses, active="generate")

        course = (request.form.get("course") or "").strip()
        session_name = (request.form.get("session") or "").strip()
        if not course or not session_name:
            flash("Course and exam session are both required.", "error")
            return render_template("generate.html", courses=courses, active="generate"), 400

        overrides, errors = build_overrides(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("generate.html", courses=courses, active="generate"), 400

        report = cached_environment_report()
        if not report.ok:
            flash("Live generation isn't available right now: " + "; ".join(report.messages), "warning")
            return render_template("generate.html", courses=courses, active="generate"), 503

        use_critic = request.form.get("use_critic") == "on"
        draft = request.form.get("final") != "on"
        model = (request.form.get("model") or "qwen2.5:7b-instruct-q4_K_M").strip()

        job_id = jobs.start(course, session_name, bp_overrides=overrides, model=model,
                            use_critic=use_critic, draft=draft)
        return redirect(url_for("job_status", job_id=job_id))

    @app.route("/jobs/<job_id>")
    def job_status(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            abort(404)
        return render_template("job.html", job=job, active="generate")

    @app.route("/api/jobs/<job_id>")
    def job_status_api(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            abort(404)
        return {
            "id": job.id,
            "status": job.status,
            "log": job.log,
            "result": _public_result(job.result, out_root) if job.result else None,
            "error": job.error,
        }

    @app.route("/papers")
    def papers_library():
        return render_template("papers.html", papers=list_generated_papers(out_root), active="papers")

    @app.route("/papers/download/<path:relpath>")
    def download_paper(relpath: str):
        target = (out_root / relpath).resolve()
        try:
            target.relative_to(out_root.resolve())
        except ValueError:
            abort(404)
        if target.name not in ALLOWED_DOWNLOAD_NAMES or not target.is_file():
            abort(404)
        return send_from_directory(target.parent, target.name)

    @app.route("/dataset")
    def dataset():
        return render_template("dataset.html", active="dataset")

    @app.route("/status")
    def status():
        return render_template("status.html", report=cached_environment_report(), active="status")

    @app.route("/about")
    def about():
        return render_template("about.html", active="about")

    return app


def _public_result(result: dict, out_root: Path) -> dict:
    """Trim the full pipeline result to what the browser needs for the job page: the in-memory
    GeneratedPaper object (result["paper"]) never crosses the JSON boundary."""
    files = result.get("files") or {}
    rel_dir = None
    filenames: dict[str, str] = {}
    for kind, path_str in files.items():
        p = Path(path_str)
        filenames[kind] = p.name
        if rel_dir is None:
            try:
                rel_dir = p.parent.relative_to(out_root).as_posix()
            except ValueError:
                rel_dir = None
    return {
        "version": result.get("version"),
        "dir": rel_dir,
        "files": filenames,
        "validation": result.get("validation"),
        "timings": result.get("timings"),
    }
