"""Preflight check for the generation CLI: packages importable, Ollama reachable, model pulled."""
from scripts.check_environment import check_environment, DEFAULT_PACKAGES


class _StubClient:
    def __init__(self, available):
        self._available = available
        self.model = "qwen2.5:7b-instruct-q4_K_M"

    def is_available(self):
        return self._available


def test_all_pass():
    r = check_environment(client=_StubClient(True), required_packages=["json", "re"])  # stdlib, always importable
    assert r.ok is True and r.missing_packages == [] and r.ollama_reachable and r.model_available


def test_ollama_unreachable_fails_with_remediation_message():
    r = check_environment(client=_StubClient(False), required_packages=["json"])
    assert r.ok is False
    assert any("ollama pull qwen2.5:7b-instruct-q4_K_M" in m for m in r.messages)


def test_missing_package_fails_with_name():
    r = check_environment(client=_StubClient(True), required_packages=["json", "this_package_does_not_exist_xyz"])
    assert r.ok is False and "this_package_does_not_exist_xyz" in r.missing_packages
