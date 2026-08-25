from __future__ import annotations

import pytest

from oracle_gap.scoring import NvidiaBackend


def test_llama_rejects_nemotron_reasoning_switch(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "not-a-real-key")
    with pytest.raises(ValueError, match="prompted deliberation"):
        NvidiaBackend("meta/llama-3.3-70b-instruct", reasoning=True)


def test_llama_generation_config_is_nonreasoning(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "not-a-real-key")
    backend = NvidiaBackend("meta/llama-3.3-70b-instruct", max_output_tokens=512)
    assert backend.generation_config == {
        "reasoning": False,
        "reasoning_effort": None,
        "max_output_tokens": 512,
        "temperature": 0.0,
        "top_p": 1.0,
    }


def test_nemotron_records_bounded_thinking_budget(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "not-a-real-key")
    backend = NvidiaBackend(
        "nvidia/nemotron-3-nano-30b-a3b",
        max_output_tokens=512,
        reasoning=True,
        max_thinking_tokens=384,
    )
    assert backend.generation_config["reasoning"] is True
    assert backend.generation_config["max_thinking_tokens"] == 384


def test_thinking_budget_requires_room_for_final_answer(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "not-a-real-key")
    with pytest.raises(ValueError, match="smaller than max_output_tokens"):
        NvidiaBackend(
            "nvidia/nemotron-3-nano-30b-a3b",
            max_output_tokens=512,
            reasoning=True,
            max_thinking_tokens=512,
        )
