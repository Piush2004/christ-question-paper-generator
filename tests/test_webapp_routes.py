"""Integration tests for the Flask routes, using fakes for the pipeline and the environment check so
no test touches a real Ollama server or the real data/ and outputs/ directories."""
import json
import time

import pytest

from scripts.check_environment import EnvironmentReport
from src.webapp.app import create_app


def write_papers_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


@pytest.fixture
def papers_jsonl(tmp_path):
    path = tmp_path / "papers.jsonl"
    write_papers_jsonl(path, [
        {"course_code": "BCA202-3", "course_name": "Operating Systems", "course_family": "operating_systems"},
        {"course_code": "BCA431", "course_name": "Graph Theory", "course_family": "graph_theory"},
    ])
    return path


@pytest.fixture
def out_root(tmp_path):
    return tmp_path / "papers_out"


def ok_report():
    return EnvironmentReport(missing_packages=[], ollama_reachable=True, model_available=True, ok=True, messages=[])


def not_ready_report():
    return EnvironmentReport(missing_packages=[], ollama_reachable=False, model_available=False, ok=False,
                             messages=["Ollama is not reachable: start Ollama and run `ollama pull ...`."])


def make_app(papers_jsonl, out_root, run_fn=None, environment_check_fn=ok_report):
    return create_app(
        run_fn=run_fn or (lambda course, session, **k: {"version": 1, "files": {}, "validation": {"approvable": True, "checks": []}, "timings": {}}),
        environment_check_fn=environment_check_fn,
        papers_jsonl=papers_jsonl,
        out_root=out_root,
    )


def test_home_page_lists_courses_and_returns_200(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"BCA202-3" in resp.data


def test_generate_get_shows_form_with_course_options(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/generate")
    assert resp.status_code == 200
    assert b"BCA202-3" in resp.data
    assert b"BCA431" in resp.data


def test_generate_post_missing_fields_returns_400_with_error(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.post("/generate", data={"course": "", "session": ""})
    assert resp.status_code == 400
    assert b"required" in resp.data


def test_generate_post_malformed_sections_returns_400(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "November 2025", "sections": "garbage"})
    assert resp.status_code == 400
    assert b"sections" in resp.data.lower()


def test_generate_post_unknown_course_returns_400(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.post("/generate", data={"course": "NOT-A-REAL-COURSE", "session": "November 2025"})
    assert resp.status_code == 400
    assert b"Unknown course" in resp.data


def test_generate_post_session_with_path_separators_returns_400(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "../../escape"})
    assert resp.status_code == 400


def test_generate_post_unapproved_model_returns_400_without_starting_job(papers_jsonl, out_root):
    started = []

    def run_fn(course, session, **k):
        started.append(True)
        return {}

    client = make_app(papers_jsonl, out_root, run_fn=run_fn).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "November 2025", "model": "some-other-model"})
    assert resp.status_code == 400
    assert started == []


def test_generate_post_when_environment_not_ready_returns_503_without_starting_job(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root, environment_check_fn=not_ready_report).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "November 2025"})
    assert resp.status_code == 503
    assert b"not available" in resp.data or b"isn" in resp.data


def test_generate_post_success_redirects_to_job_status(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "November 2025"})
    assert resp.status_code == 302
    assert "/jobs/" in resp.headers["Location"]


def test_job_status_page_and_api_reflect_completed_job(papers_jsonl, out_root):
    out_root.mkdir(parents=True)

    def fake_run(course, session, progress=None, **kwargs):
        if progress:
            progress("history", 1, 2)
            progress("generation", 2, 2)
        d = out_root / "BCA202-3_November2025" / "v1"
        d.mkdir(parents=True)
        (d / "paper.pdf").write_bytes(b"%PDF-fake")
        (d / "paper.docx").write_bytes(b"docx-fake")
        return {
            "version": 1,
            "files": {"pdf": str(d / "paper.pdf"), "docx": str(d / "paper.docx")},
            "validation": {"approvable": True, "checks": [{"name": "marks", "passed": True, "detail": "ok"}]},
            "timings": {"generation_s": 0.01},
        }

    client = make_app(papers_jsonl, out_root, run_fn=fake_run).test_client()
    resp = client.post("/generate", data={"course": "BCA202-3", "session": "November 2025"})
    job_url = resp.headers["Location"]
    job_id = job_url.rstrip("/").rsplit("/", 1)[-1]

    page = client.get(job_url)
    assert page.status_code == 200

    deadline = time.time() + 2.0
    data = {}
    while time.time() < deadline:
        api_resp = client.get(f"/api/jobs/{job_id}")
        data = api_resp.get_json()
        if data["status"] == "done":
            break
        time.sleep(0.01)
    assert data["status"] == "done"
    assert data["log"] == ["[1/2] history", "[2/2] generation"]
    assert data["result"]["version"] == 1
    assert data["result"]["dir"] == "BCA202-3_November2025/v1"
    assert data["result"]["files"] == {"pdf": "paper.pdf", "docx": "paper.docx"}
    assert data["result"]["validation"]["approvable"] is True


def test_job_status_unknown_id_returns_404(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    assert client.get("/jobs/does-not-exist").status_code == 404
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_papers_library_lists_generated_papers(papers_jsonl, out_root):
    d = out_root / "BCA202-3_November2025" / "v1"
    d.mkdir(parents=True)
    (d / "paper.json").write_text(json.dumps({
        "course_code": "BCA202-3", "exam_session": "November 2025", "version": 1,
        "validation": {"approvable": True},
    }), encoding="utf-8")
    (d / "paper.pdf").write_bytes(b"%PDF-fake")

    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/papers")
    assert resp.status_code == 200
    assert b"BCA202-3" in resp.data


def test_download_paper_serves_allowed_file(papers_jsonl, out_root):
    d = out_root / "BCA202-3_November2025" / "v1"
    d.mkdir(parents=True)
    (d / "paper.pdf").write_bytes(b"%PDF-fake-bytes")

    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/papers/download/BCA202-3_November2025/v1/paper.pdf")
    assert resp.status_code == 200
    assert resp.data == b"%PDF-fake-bytes"


def test_download_paper_rejects_path_traversal(papers_jsonl, out_root):
    out_root.mkdir(parents=True)
    secret = out_root.parent / "secret.txt"
    secret.write_text("sensitive", encoding="utf-8")

    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/papers/download/../secret.txt")
    assert resp.status_code == 404


def test_download_paper_rejects_disallowed_filename(papers_jsonl, out_root):
    d = out_root / "BCA202-3_November2025" / "v1"
    d.mkdir(parents=True)
    (d / "not_allowed.txt").write_text("x", encoding="utf-8")

    client = make_app(papers_jsonl, out_root).test_client()
    resp = client.get("/papers/download/BCA202-3_November2025/v1/not_allowed.txt")
    assert resp.status_code == 404


def test_dataset_page_returns_200(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    assert client.get("/dataset").status_code == 200


def test_status_page_reflects_environment_report(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root, environment_check_fn=not_ready_report).test_client()
    resp = client.get("/status")
    assert resp.status_code == 200
    assert b"showcase mode" in resp.data.lower()


def test_about_page_returns_200(papers_jsonl, out_root):
    client = make_app(papers_jsonl, out_root).test_client()
    assert client.get("/about").status_code == 200
