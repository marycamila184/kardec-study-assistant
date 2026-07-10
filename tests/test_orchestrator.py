from unittest.mock import MagicMock

import pytest

from src.rag.orchestrator import classify_intent


def _mock_client(monkeypatch, content):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.orchestrator.get_client", lambda: client)
    return client


def test_classify_returns_refletir_for_emotional_message(monkeypatch):
    _mock_client(monkeypatch, '{"mode": "refletir", "confidence": "high"}')
    result = classify_intent("estou muito mal, me ajuda", current_mode="tirar_duvida")
    assert result["mode"] == "refletir"


def test_classify_never_nudges_to_current_mode(monkeypatch):
    _mock_client(monkeypatch, '{"mode": "refletir", "confidence": "high"}')
    result = classify_intent("estou muito mal", current_mode="refletir")
    assert result["mode"] is None


def test_classify_suppresses_on_low_confidence(monkeypatch):
    _mock_client(monkeypatch, '{"mode": "estudar_obra", "confidence": "low"}')
    result = classify_intent("algo vago", current_mode="tirar_duvida")
    assert result["mode"] is None


def test_classify_crisis_short_circuits_without_llm(monkeypatch):
    def _boom():
        raise AssertionError("LLM must not run on crisis")

    monkeypatch.setattr("src.rag.orchestrator.get_client", _boom)
    result = classify_intent("penso em me matar", current_mode="tirar_duvida")
    assert result["mode"] is None


def test_classify_smalltalk_short_circuits_without_llm(monkeypatch):
    def _boom():
        raise AssertionError("LLM must not run on small talk")

    monkeypatch.setattr("src.rag.orchestrator.get_client", _boom)
    result = classify_intent("obrigada", current_mode="tirar_duvida")
    assert result["mode"] is None


def test_classify_failure_returns_no_nudge(monkeypatch):
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("boom")
    monkeypatch.setattr("src.rag.orchestrator.get_client", lambda: client)
    result = classify_intent("o que é o perispírito?", current_mode="refletir")
    assert result["mode"] is None


def test_classify_invalid_mode_string_is_dropped(monkeypatch):
    _mock_client(monkeypatch, '{"mode": "banana", "confidence": "high"}')
    result = classify_intent("mensagem", current_mode="tirar_duvida")
    assert result["mode"] is None
