"""The hosted embedding lane must be bounded and survive one provider hanging.

Measured 2026-08-03 against OpenRouter: 3 of 14 single-query calls took 32s,
32s and 111s while the rest answered in 0.4-2.2s. The call sits on the critical
path of every /chat and /study — nothing is retrieved until the question is
embedded — so an unbounded wait there is the whole request.
"""

from unittest.mock import MagicMock

import pytest

from src.ingestion import embeddings


def _vectors(n):
    return MagicMock(data=[MagicMock(embedding=[0.1] * 1024) for _ in range(n)])


class _Recorder:
    """Stands in for OpenAI(...), capturing how the client was built."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.embeddings = MagicMock()
        self.embeddings.create = lambda model, input: _vectors(len(input))


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(embeddings.settings, "openrouter_api_key", "k")
    monkeypatch.setattr(embeddings.settings, "deepinfra_api_key", None)
    monkeypatch.setattr(embeddings.settings, "novita_api_key", None)


def test_hosted_client_is_built_with_a_finite_timeout_and_retries(hosted, monkeypatch):
    """The SDK default is read=600s with 2 retries — up to 30 minutes on one
    call, while Cloud Run gives up at 120s. An unbounded client cannot stay."""
    built = []

    def fake_openai(**kwargs):
        built.append(kwargs)
        return _Recorder(**kwargs)

    monkeypatch.setattr(embeddings, "_new_openai", fake_openai)
    embeddings.encode(["uma pergunta"])

    assert built, "the hosted lane must build a client"
    timeout = built[0]["timeout"]
    assert timeout is not None and timeout < 60, f"unbounded timeout: {timeout}"
    assert built[0]["max_retries"] >= 1, "a hang must be retried, not just failed"


def test_timeout_scales_with_the_batch(hosted, monkeypatch):
    """One query and a 100-chunk ingestion batch cannot share a budget: the
    budget that keeps a request snappy would abort the corpus pass."""
    built = []
    monkeypatch.setattr(
        embeddings, "_new_openai", lambda **kw: built.append(kw) or _Recorder(**kw)
    )

    embeddings.encode(["só uma"])
    one = built[-1]["timeout"]
    embeddings.encode([f"t{i}" for i in range(embeddings.HOSTED_BATCH_MAX)])
    many = built[-1]["timeout"]

    assert many > one, "a full batch needs more room than a single query"


def test_a_hanging_provider_falls_over_to_the_next(hosted, monkeypatch):
    """Same model on another host beats no answer at all."""
    monkeypatch.setattr(embeddings.settings, "deepinfra_api_key", "k2")
    seen = []

    def client_for(provider, timeout):
        seen.append(provider)
        c = MagicMock()
        if provider == "openrouter":
            c.embeddings.create.side_effect = TimeoutError("hung")
        else:
            c.embeddings.create.side_effect = lambda model, input: _vectors(len(input))
        return c

    monkeypatch.setattr(embeddings, "_hosted_client", client_for)
    out = embeddings.encode(["pergunta"])

    assert len(out) == 1
    assert seen == ["openrouter", "deepinfra"], f"chain was {seen}"


def test_failover_never_changes_the_model(hosted, monkeypatch):
    """Parity was measured for bge-m3 against the stored vectors. A provider
    serving anything else would land queries in a different space, and Chroma
    would store the mismatch happily — so it must never be a fallback."""
    monkeypatch.setattr(embeddings.settings, "novita_api_key", "k3")
    monkeypatch.setitem(
        embeddings.EMBEDDING_PROVIDERS,
        "novita",
        ("https://api.novita.ai/v3/openai", "novita_api_key", "some/other-model"),
    )
    assert "novita" not in embeddings._provider_chain()


def test_every_provider_failing_still_raises(hosted, monkeypatch):
    """Silence here surfaces weeks later as 'the answers got vaguer'."""
    monkeypatch.setattr(embeddings.settings, "deepinfra_api_key", "k2")

    def always_hangs(provider, timeout):
        c = MagicMock()
        c.embeddings.create.side_effect = TimeoutError("hung")
        return c

    monkeypatch.setattr(embeddings, "_hosted_client", always_hangs)
    with pytest.raises(Exception):
        embeddings.encode(["pergunta"])


def test_a_short_response_raises_instead_of_failing_over(hosted, monkeypatch):
    """A wrong number of vectors is a correctness fault, not a transport one —
    retrying it elsewhere would paper over a misalignment of every id."""
    monkeypatch.setattr(embeddings.settings, "deepinfra_api_key", "k2")
    tried = []

    def client_for(provider, timeout):
        tried.append(provider)
        c = MagicMock()
        c.embeddings.create.side_effect = lambda model, input: _vectors(1)
        return c

    monkeypatch.setattr(embeddings, "_hosted_client", client_for)
    with pytest.raises(RuntimeError, match="2 textos"):
        embeddings.encode(["a", "b"])
    assert tried == ["openrouter"], "must not have tried the fallback"
