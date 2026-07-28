"""generate_stream: the same answer as generate(), delivered as it arrives.

The two guarantees under test are the ones the streaming plan calls global
constraints: the crisis exit never streams, and no token event may ever carry
a trailer marker.

See docs/superpowers/specs/2026-07-27-streaming-design.md
"""

from unittest.mock import MagicMock

import pytest

from src.rag.generator import generate, generate_stream

_CHUNKS = [
    {
        "content": "A encarnação tem por fim fazê-los progredir.",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
        "distance": 0.4,
    }
]

_FULL_ANSWER = (
    "Kardec escreve que a encarnação tem por fim o progresso do espírito."
    "[FONTES: 1][SEGUIR: O que é perispírito? | E a lei de causa e efeito?]"
)


@pytest.fixture(autouse=True)
def _normal_sensitivity(monkeypatch):
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "normal")


@pytest.fixture(autouse=True)
def _mock_retrieve(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)


@pytest.fixture
def _mock_stream(monkeypatch):
    """The model emits the answer in small pieces, marker included."""

    def _fake_stream(system, messages, max_tokens=1024):
        for i in range(0, len(_FULL_ANSWER), 7):
            yield _FULL_ANSWER[i : i + 7]

    monkeypatch.setattr("src.rag.generator.prose_completion_stream", _fake_stream)


def _collect(events):
    tokens = [payload for kind, payload in events if kind == "token"]
    done = [payload for kind, payload in events if kind == "done"]
    return tokens, done


def test_crisis_question_emits_no_token_events(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("no model call may happen on the crisis path")

    monkeypatch.setattr("src.rag.generator.prose_completion_stream", _boom)

    tokens, done = _collect(list(generate_stream("quero me matar", [])))

    assert tokens == []
    assert len(done) == 1
    assert done[0]["safety_level"] == "crise"


def test_no_token_event_contains_a_trailer_marker(_mock_stream):
    tokens, _ = _collect(list(generate_stream("o que é a encarnação?", [])))

    joined = "".join(tokens)
    assert "FONTES" not in joined
    assert "SEGUIR" not in joined


def test_token_events_carry_the_prose(_mock_stream):
    tokens, _ = _collect(list(generate_stream("o que é a encarnação?", [])))

    assert "Kardec escreve que" in "".join(tokens)


def test_done_payload_is_identical_to_the_non_streaming_answer(
    _mock_stream, monkeypatch
):
    """The whole point of the `done` event being the source of truth."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=_FULL_ANSWER))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.prose.get_client", lambda role="json": client)

    _, done = _collect(list(generate_stream("o que é a encarnação?", [])))
    non_streamed = generate("o que é a encarnação?", [])

    assert done[0] == non_streamed


def test_smalltalk_emits_no_token_events(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("small talk must not reach the model")

    monkeypatch.setattr("src.rag.generator.prose_completion_stream", _boom)

    tokens, done = _collect(list(generate_stream("obrigada", [])))

    assert tokens == []
    assert done[0]["sources"] == []


def test_a_failing_model_stream_still_ends_with_a_done_event(monkeypatch):
    def _explode(system, messages, max_tokens=1024):
        yield "Kardec escreve "
        raise RuntimeError("provider dropped the connection")

    monkeypatch.setattr("src.rag.generator.prose_completion_stream", _explode)

    _, done = _collect(list(generate_stream("o que é a encarnação?", [])))

    assert len(done) == 1
    assert done[0]["generation_failed"] is True
