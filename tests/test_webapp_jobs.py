"""JobManager: runs a long function (pipeline.run) on a background thread, exposing live progress
and a terminal state for the web layer to poll — no request ever blocks on generation."""
import threading
import time

from src.webapp.jobs import JobManager


def _wait_until_terminal(manager, job_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(job_id)
        if job.status in ("done", "error"):
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach a terminal state in {timeout}s")


def test_unknown_job_id_returns_none():
    manager = JobManager(run_fn=lambda *a, **k: {})
    assert manager.get("nope") is None


def test_start_returns_a_job_id_immediately_without_blocking():
    started = threading.Event()
    release = threading.Event()

    def slow_run(course, session, **kwargs):
        started.set()
        release.wait(timeout=2.0)
        return {"ok": True}

    manager = JobManager(run_fn=slow_run)
    job_id = manager.start("BCA202-3", "November 2025")
    assert started.wait(timeout=1.0)
    job = manager.get(job_id)
    assert job is not None
    assert job.status in ("queued", "running")
    release.set()


def test_successful_job_reaches_done_with_result():
    manager = JobManager(run_fn=lambda course, session, **k: {"version": 1, "course": course})
    job_id = manager.start("BCA202-3", "November 2025")
    job = _wait_until_terminal(manager, job_id)
    assert job.status == "done"
    assert job.result == {"version": 1, "course": "BCA202-3"}
    assert job.error is None


def test_job_error_detail_redacts_credentials_embedded_in_a_url():
    """job.error is served verbatim by the public /api/jobs/<id> endpoint. If OLLAMA_HOST ever carries
    embedded credentials (e.g. behind an authenticated reverse proxy) and a request to it fails, the
    exception text must not leak them to that unauthenticated endpoint."""
    def boom(course, session, **k):
        raise ConnectionError("Ollama request failed: https://admin:s3cr3t@ollama.example.com/api/chat")

    manager = JobManager(run_fn=boom)
    job_id = manager.start("BCA202-3", "November 2025")
    job = _wait_until_terminal(manager, job_id)
    assert "s3cr3t" not in job.error["detail"]
    assert "admin" not in job.error["detail"]
    assert "ollama.example.com" in job.error["detail"]  # host kept — only the credentials are stripped


def test_failing_job_reaches_error_with_detail():
    def boom(course, session, **k):
        raise ValueError("no such course")

    manager = JobManager(run_fn=boom)
    job_id = manager.start("nonexistent", "November 2025")
    job = _wait_until_terminal(manager, job_id)
    assert job.status == "error"
    assert job.error["type"] == "ValueError"
    assert job.error["detail"] == "no such course"
    assert job.result is None


def test_progress_callback_appends_log_lines_in_order():
    def run_with_progress(course, session, progress=None, **k):
        progress("history", 1, 3)
        progress("allocation", 2, 3)
        progress("generation", 3, 3)
        return {"done": True}

    manager = JobManager(run_fn=run_with_progress)
    job_id = manager.start("BCA202-3", "November 2025")
    job = _wait_until_terminal(manager, job_id)
    assert job.log == ["[1/3] history", "[2/3] allocation", "[3/3] generation"]


def test_max_concurrent_jobs_bounds_simultaneous_execution():
    """A publicly hosted instance must not let an unbounded number of Generate submissions each spawn
    their own expensive LLM run at once — JobManager caps how many run_fn calls execute simultaneously,
    queuing the rest."""
    gate = threading.Event()
    lock = threading.Lock()
    state = {"running": 0, "max_seen": 0}

    def run_fn(course, session, **k):
        with lock:
            state["running"] += 1
            state["max_seen"] = max(state["max_seen"], state["running"])
        gate.wait(timeout=2.0)
        with lock:
            state["running"] -= 1
        return {}

    manager = JobManager(run_fn=run_fn, max_concurrent=2)
    job_ids = [manager.start(f"C{i}", "November 2025") for i in range(5)]

    deadline = time.time() + 2.0
    while time.time() < deadline and state["running"] < 2:
        time.sleep(0.01)
    assert state["running"] == 2

    gate.set()
    for job_id in job_ids:
        _wait_until_terminal(manager, job_id)
    assert state["max_seen"] == 2


def test_run_fn_receives_extra_keyword_overrides():
    received = {}

    def run_fn(course, session, progress=None, **kwargs):
        received.update(kwargs)
        return {}

    manager = JobManager(run_fn=run_fn)
    job_id = manager.start("BCA202-3", "November 2025", model="qwen2.5:7b-instruct-q4_K_M", use_critic=False)
    _wait_until_terminal(manager, job_id)
    assert received == {"model": "qwen2.5:7b-instruct-q4_K_M", "use_critic": False}
