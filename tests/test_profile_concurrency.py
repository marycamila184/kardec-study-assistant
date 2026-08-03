"""Profile detection must not be a blocking prelude to the answer.

It used to run to completion before anything else started: an LLM call with a
3s budget, in front of condensation, embedding and retrieval, none of which
need its result. Production was logging its TimeoutError, so readers were
paying the full 3s *and* getting the unchanged profile anyway.

The profile is only needed when the prompt is built, which is the last thing
`_prepare` does — so it is passed in as something to resolve, and resolved
there. Everything before it overlaps.
"""

from unittest.mock import MagicMock

import pytest

from src.rag import generator
from src.rag.profile import CHAT_DEFAULT

_CHUNKS = [
    {
        "content": "A prece é um ato de adoração.",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter_title": "Da Prece",
            "chapter": "CAPÍTULO XXVII",
            "item_number": "9",
        },
        "distance": 0.4,
    }
]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "normal")
    monkeypatch.setattr("src.rag.generator.condense_query", lambda q, h: q)
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Resposta."))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.prose.get_client", lambda role="json": client)


def test_the_profile_is_resolved_after_retrieval_not_before(monkeypatch):
    """The ordering IS the latency fix: whatever produces the profile gets the
    whole retrieval round trip to finish in."""
    order = []

    def retrieve(q, **kw):
        order.append("retrieve")
        return _CHUNKS

    monkeypatch.setattr("src.rag.generator.retrieve", retrieve)

    def deferred():
        order.append("profile")
        return CHAT_DEFAULT

    generator.generate("O que é a prece?", [], profile=deferred)

    assert order, "nothing ran"
    assert order.index("retrieve") < order.index(
        "profile"
    ), f"profile still blocks retrieval: {order}"


def _spy_on_build_messages(monkeypatch):
    """Captures the profile that actually reached the prompt — the only place it
    is used, and therefore the only place worth asserting on."""
    seen = []
    real = generator.build_messages

    def spy(*args, **kwargs):
        seen.append(kwargs.get("profile"))
        return real(*args, **kwargs)

    monkeypatch.setattr(generator, "build_messages", spy)
    return seen


def test_a_plain_profile_still_works(monkeypatch):
    """Every existing caller and test passes a ResponseProfile, not a callable."""
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)
    seen = _spy_on_build_messages(monkeypatch)
    generator.generate("O que é a prece?", [], profile=CHAT_DEFAULT)
    assert seen == [CHAT_DEFAULT]


def test_the_profile_is_resolved_exactly_once(monkeypatch):
    """It is read for the prompt and reported on the response; resolving twice
    would mean two LLM calls, or two different answers to the same question."""
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)
    calls = []

    def deferred():
        calls.append(1)
        return CHAT_DEFAULT

    generator.generate("O que é a prece?", [], profile=deferred)
    assert len(calls) == 1, f"resolved {len(calls)} times"


def test_a_failing_resolver_never_breaks_the_answer(monkeypatch):
    """A classifier that cannot answer must not cost the reader their answer."""
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)

    def boom():
        raise RuntimeError("detector down")

    seen = _spy_on_build_messages(monkeypatch)
    out = generator.generate("O que é a prece?", [], profile=boom)
    assert out["answer"], "the answer must survive a failed profile resolution"
    assert seen == [CHAT_DEFAULT], "a dead detector must leave the default in place"
