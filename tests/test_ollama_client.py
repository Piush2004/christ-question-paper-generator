"""OllamaClient's base_url must be configurable via the OLLAMA_HOST environment variable so a
deployed instance (no local Ollama available) can point live generation at a reachable server
without a code change."""
from src.llm.ollama import DEFAULT_URL, OllamaClient


def test_base_url_defaults_to_localhost_without_the_env_var(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert OllamaClient().base_url == DEFAULT_URL


def test_base_url_reads_ollama_host_env_var(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://remote-ollama:11434")
    assert OllamaClient().base_url == "http://remote-ollama:11434"


def test_explicit_base_url_argument_overrides_the_env_var(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://remote-ollama:11434")
    assert OllamaClient(base_url="http://other-host:1234").base_url == "http://other-host:1234"
