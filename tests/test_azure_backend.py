from __future__ import annotations

import pytest

from oracle_gap.scoring import AzureOpenAIBackend


def test_azure_backend_requires_all_environment_values(monkeypatch):
    for name in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        AzureOpenAIBackend()


def test_azure_backend_normalizes_v1_endpoint(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.services.ai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    backend = AzureOpenAIBackend(max_output_tokens=180, reasoning_effort="none")
    assert backend.base_url == "https://example.services.ai.azure.com/openai/v1"
    assert backend.model == "gpt-5-mini"
    assert backend.generation_config["reasoning_effort"] == "none"
    assert backend.generation_config["reasoning"] is False


def test_azure_backend_accepts_full_responses_endpoint(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.services.ai.azure.com/openai/v1/responses",
    )
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    backend = AzureOpenAIBackend()
    assert backend.base_url == "https://example.services.ai.azure.com/openai/v1"


def test_azure_output_text_parses_response_items():
    value = {"output": [{"content": [{"type": "output_text", "text": "hello"}]}]}
    assert AzureOpenAIBackend._output_text(value) == "hello"
