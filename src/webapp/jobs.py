"""Background job runner for the web app: a generation request (`pipeline.run`, which can take minutes
of LLM calls) must never block the HTTP request that starts it. `JobManager.start()` returns immediately
with a job id; the caller polls `get(job_id)` for live progress and the terminal result or error."""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# job.error is served verbatim by the public /api/jobs/<id> endpoint. If a URL embedded in an
# exception message (e.g. OLLAMA_HOST pointed at an authenticated proxy) carries credentials,
# strip them before they ever reach that unauthenticated endpoint.
_URL_CREDENTIALS = re.compile(r"://[^/@\s]+@")


def _redact_credentials(text: str) -> str:
    return _URL_CREDENTIALS.sub("://", text)


@dataclass
class Job:
    id: str
    course: str
    session: str
    status: str = "queued"  # queued -> running -> done | error
    log: list[str] = field(default_factory=list)
    result: dict | None = None
    error: dict[str, Any] | None = None


class JobManager:
    def __init__(self, run_fn: Callable[..., dict], max_concurrent: int = 2):
        self._run_fn = run_fn
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(max_concurrent)

    def start(self, course: str, session: str, **run_kwargs: Any) -> str:
        job = Job(id=uuid.uuid4().hex, course=course, session=session)
        with self._lock:
            self._jobs[job.id] = job
        threading.Thread(target=self._execute, args=(job, run_kwargs), daemon=True).start()
        return job.id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _execute(self, job: Job, run_kwargs: dict[str, Any]) -> None:
        with self._slots:  # bounds how many run_fn calls (expensive LLM work) run at once; the rest
                           # of the queue stays in "queued" status until a slot frees up
            job.status = "running"

            def progress(label: str, i: int, n: int) -> None:
                job.log.append(f"[{i}/{n}] {label}")

            try:
                job.result = self._run_fn(job.course, job.session, progress=progress, **run_kwargs)
                job.status = "done"
            except Exception as exc:
                job.error = {"type": type(exc).__name__, "detail": _redact_credentials(str(exc)),
                            "problems": getattr(exc, "problems", None)}
                job.status = "error"
