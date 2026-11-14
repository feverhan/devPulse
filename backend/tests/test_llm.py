from __future__ import annotations

from app.services.llm import LLMConfig


def test_normalized_base_appends_v1():
    assert LLMConfig(base_url="http://127.0.0.1:8000").normalized_base == "http://127.0.0.1:8000/v1"


def test_normalized_base_keeps_existing_v1():
    assert LLMConfig(base_url="http://127.0.0.1:8000/v1").normalized_base == "http://127.0.0.1:8000/v1"


def test_normalized_base_handles_openai_suffix():
    assert LLMConfig(base_url="http://host/openai").normalized_base == "http://host/openai/v1"


def test_normalized_base_strips_trailing_slash():
    assert LLMConfig(base_url="http://host/v1/").normalized_base == "http://host/v1"


def test_ready_requires_base_and_model():
    assert not LLMConfig(base_url="http://host", model="").ready
    assert not LLMConfig(base_url="", model="qwen").ready
    assert LLMConfig(base_url="http://host", model="qwen").ready