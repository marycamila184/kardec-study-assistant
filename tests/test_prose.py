from unittest.mock import MagicMock, patch

import pytest

from src.rag.prose import prose_completion

_SYS = "system prompt"
_MSGS = [{"role": "user", "content": "pergunta"}]


def _client_returning(text):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=text))
    ]
    return client


def _client_raising(exc):
    client = MagicMock()
    client.chat.completions.create.side_effect = exc
    return client


def test_returns_prose_lane_output():
    client = _client_returning("resposta do riv-ai")
    with patch("src.rag.prose.get_client", return_value=client):
        assert prose_completion(_SYS, _MSGS) == "resposta do riv-ai"


def test_pins_temperature_to_zero_on_the_prose_lane():
    """Grounding depends on it — see the smoke-test findings in the spec."""
    client = _client_returning("ok")
    with (
        patch("src.rag.prose.get_client", return_value=client),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = "ollama"
        prose_completion(_SYS, _MSGS)
    assert client.chat.completions.create.call_args.kwargs["temperature"] == 0


def test_omits_temperature_while_the_prose_lane_is_off():
    """Pinning it here would change the current provider's output before the
    lane is ever switched on."""
    client = _client_returning("ok")
    with (
        patch("src.rag.prose.get_client", return_value=client),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = None
        prose_completion(_SYS, _MSGS)
    assert "temperature" not in client.chat.completions.create.call_args.kwargs


def test_uses_the_prose_model():
    client = _client_returning("ok")
    with (
        patch("src.rag.prose.get_client", return_value=client),
        patch("src.rag.prose.settings") as s,
    ):
        s.resolved_prose_model = "riv-ai-v2"
        s.resolved_chat_model = "llama-3.3-70b-versatile"
        prose_completion(_SYS, _MSGS)
    assert client.chat.completions.create.call_args.kwargs["model"] == "riv-ai-v2"


def test_falls_back_to_json_lane_when_prose_lane_fails():
    """Ollama being down must degrade to today's provider, never to a 500."""
    prose = _client_raising(ConnectionError("connection refused"))
    fallback = _client_returning("resposta do 70B")

    def _by_role(role="json"):
        return prose if role == "prose" else fallback

    with (
        patch("src.rag.prose.get_client", side_effect=_by_role),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = "ollama"
        assert prose_completion(_SYS, _MSGS) == "resposta do 70B"


def test_fallback_uses_the_chat_model():
    prose = _client_raising(ConnectionError("down"))
    fallback = _client_returning("ok")

    def _by_role(role="json"):
        return prose if role == "prose" else fallback

    with (
        patch("src.rag.prose.get_client", side_effect=_by_role),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = "ollama"
        s.resolved_prose_model = "riv-ai-v2"
        s.resolved_chat_model = "llama-3.3-70b-versatile"
        prose_completion(_SYS, _MSGS)
    assert (
        fallback.chat.completions.create.call_args.kwargs["model"]
        == "llama-3.3-70b-versatile"
    )


def test_raises_when_both_lanes_fail():
    """Lanes differ (PROSE_PROVIDER set) but both the prose lane and the
    fallback json lane fail: the exception must still propagate, and both
    lanes must have been tried — the caller's existing generation_failed
    handling owns this case."""
    client = _client_raising(ConnectionError("down"))
    with (
        patch("src.rag.prose.get_client", return_value=client),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = "ollama"
        with pytest.raises(ConnectionError):
            prose_completion(_SYS, _MSGS)
    assert client.chat.completions.create.call_count == 2


def test_no_fallback_call_when_lanes_are_the_same():
    """PROSE_PROVIDER unset: one provider, so a failure must not be retried."""
    client = _client_raising(ConnectionError("down"))
    with (
        patch("src.rag.prose.get_client", return_value=client),
        patch("src.rag.prose.settings") as s,
    ):
        s.prose_provider = None
        s.resolved_prose_model = "llama-3.3-70b-versatile"
        s.resolved_chat_model = "llama-3.3-70b-versatile"
        with pytest.raises(ConnectionError):
            prose_completion(_SYS, _MSGS)
    assert client.chat.completions.create.call_count == 1
