from unittest.mock import MagicMock

from src.rag.orchestrator import classify_intent


def _mock_client(monkeypatch, content):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.orchestrator.get_client", lambda: client)
    return client


def test_classify_drops_refletir_even_if_llm_suggests_it(monkeypatch):
    # Refletir is switched off (see docs/superpowers/specs/2026-07-26-desligar-
    # reflexivo-design.md): "refletir" is no longer in _VALID_MODES, so a model
    # that still emits it (an old prompt cache, a hallucination) gets filtered
    # to no nudge rather than routing to a dead route.
    _mock_client(monkeypatch, '{"mode": "refletir", "confidence": "high"}')
    result = classify_intent("estou muito mal, me ajuda", current_mode="tirar_duvida")
    assert result["mode"] is None


def test_classify_includes_history_in_prompt(monkeypatch):
    client = _mock_client(monkeypatch, '{"mode": "refletir", "confidence": "high"}')
    history = [
        {"role": "user", "content": "perdi minha mãe"},
        {"role": "assistant", "content": "sinto muito"},
    ]
    classify_intent("e sobre isso?", current_mode="tirar_duvida", history=history)
    sent = client.chat.completions.create.call_args.kwargs["messages"]
    user_content = sent[-1]["content"]
    assert "perdi minha mãe" in user_content
    assert "e sobre isso?" in user_content


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


def test_never_nudges_to_the_disabled_reflect_mode():
    """A nudge to a mode with no route is a dead end for the reader."""
    from src.rag.orchestrator import _VALID_MODES

    assert "refletir" not in _VALID_MODES


def test_system_prompt_marks_clarification_as_not_refletir():
    from src.rag.orchestrator import _SYSTEM_PROMPT

    # A doctrinal clarification question must be steered to tirar_duvida, not
    # refletir, even when the topic sounds personal.
    assert "esclarecimento" in _SYSTEM_PROMPT
    assert "quer dizer que" in _SYSTEM_PROMPT


def test_no_nudge_out_of_estudar_and_no_llm_call_to_find_that_out(monkeypatch):
    """From Estudar the only target this could ever emit is `tirar_duvida` —
    it never nudges toward the current mode — and that button was removed.

    Measured 2026-08-03, and it was firing backwards from its own purpose: the
    button existed for the reader who slides from studying into something
    Estudar cannot shape (grief), yet "perdi minha mãe e não consigo trabalhar"
    produced no nudge while "o que seria necessidades humanas?" — a follow-up
    about the passage on screen — produced one at high confidence. Acting on it
    moved readers out of the mode that was serving them, into a fresh /chat that
    no longer had the passage.

    So the classification is skipped, not just discarded: it is an LLM call per
    turn whose answer nobody can act on.
    """
    client = _mock_client(monkeypatch, '{"mode": "tirar_duvida", "confidence": "high"}')
    result = classify_intent("o que seria necessidades humanas?", "estudar_obra")
    assert result["mode"] is None
    assert not client.chat.completions.create.called, "no LLM call should be made"


def test_the_other_direction_still_nudges(monkeypatch):
    """Dialogar -> Estudar is the deepening move and stays: it hands over an
    identifier, which `retrieve_by_item` looks up deterministically, so unlike
    the removed direction it cannot lose the reader's context."""
    _mock_client(monkeypatch, '{"mode": "estudar_obra", "confidence": "high"}')
    result = classify_intent("explique a questão 132", "tirar_duvida")
    assert result["mode"] == "estudar_obra"


def test_the_daily_passage_still_gets_its_invitation(monkeypatch):
    """The daily-passage call passes current_mode=None deliberately — there the
    invitation to open the item in full is the point."""
    _mock_client(monkeypatch, '{"mode": "estudar_obra", "confidence": "high"}')
    assert classify_intent("Explique este trecho", None)["mode"] == "estudar_obra"
