"""next_version_dir() composes its output directory name directly from caller-supplied course code and
session strings. Those now reach it from a web form (src/webapp/app.py), not only from a trusted CLI
argv, so a path-separator or '..' sequence in either must be rejected before any directory is created
— never silently written outside outputs/papers/."""
import pytest

from src.generation.pipeline import next_version_dir


def test_next_version_dir_creates_v1_for_a_new_course_session(tmp_path, monkeypatch):
    monkeypatch.setattr("src.generation.pipeline.OUT_ROOT", tmp_path)
    d, v = next_version_dir("BCA202-3", "November 2025")
    assert v == 1
    assert d == tmp_path / "BCA202-3_November2025" / "v1"
    assert d.is_dir()


def test_next_version_dir_increments_version_on_repeat_calls(tmp_path, monkeypatch):
    monkeypatch.setattr("src.generation.pipeline.OUT_ROOT", tmp_path)
    next_version_dir("BCA202-3", "November 2025")
    _, v2 = next_version_dir("BCA202-3", "November 2025")
    assert v2 == 2


@pytest.mark.parametrize("session", ["../../escape", "a/b", "a\\b", "foo/../bar", "x\x00y"])
def test_next_version_dir_rejects_unsafe_session(tmp_path, monkeypatch, session):
    monkeypatch.setattr("src.generation.pipeline.OUT_ROOT", tmp_path)
    with pytest.raises(ValueError):
        next_version_dir("BCA202-3", session)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("code", ["../escape", "a/b", "a\\b"])
def test_next_version_dir_rejects_unsafe_course_code(tmp_path, monkeypatch, code):
    monkeypatch.setattr("src.generation.pipeline.OUT_ROOT", tmp_path)
    with pytest.raises(ValueError):
        next_version_dir(code, "November 2025")
    assert list(tmp_path.iterdir()) == []
