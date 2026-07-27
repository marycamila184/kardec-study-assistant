from src.ingestion.embeddings import encode


def test_encode_returns_one_vector_per_input():
    results = encode(["reencarnação", "alma espírita"])
    assert len(results) == 2


def test_encode_vector_dimension_is_1024():
    results = encode(["qualquer texto"])
    assert len(results[0]) == 1024  # BAAI/bge-m3


def test_encode_same_text_is_deterministic():
    a = encode(["Deus"])
    b = encode(["Deus"])
    assert a == b


def test_local_lane_is_the_default_and_never_calls_the_network(monkeypatch):
    """Unset EMBEDDING_PROVIDER must be byte-for-byte today's behavior.

    The hosted lane is opt-in until scripts/verify_embedding_parity.py says the
    vectors land in the same space; a default that silently went hosted would
    change retrieval without anyone choosing it.
    """
    from src.ingestion import embeddings

    monkeypatch.setattr(embeddings.settings, "embedding_provider", None)
    called = []
    monkeypatch.setattr(
        embeddings, "_encode_hosted", lambda texts: called.append(texts) or [[0.0]]
    )

    class FakeModel:
        def encode(self, texts, convert_to_numpy=True):
            import numpy as np

            return np.zeros((len(texts), 1024))

    monkeypatch.setattr(embeddings, "_get_model", lambda: FakeModel())
    out = embeddings.encode(["a", "b"])
    assert called == [], "a via local não pode tocar a rede"
    assert len(out) == 2 and len(out[0]) == 1024


def test_hosted_lane_batches_and_refuses_a_short_response(monkeypatch):
    """A short response would misalign every id in the batch, and a wrong vector
    raises nothing downstream — Chroma stores it and retrieval just gets worse."""
    import pytest

    from src.ingestion import embeddings

    monkeypatch.setattr(embeddings.settings, "embedding_provider", "deepinfra")
    monkeypatch.setattr(embeddings.settings, "deepinfra_api_key", "k")
    sizes = []

    class FakeClient:
        class embeddings:  # noqa: N801
            @staticmethod
            def create(model, input):
                sizes.append(len(input))
                from unittest.mock import MagicMock

                return MagicMock(
                    data=[MagicMock(embedding=[0.1] * 1024) for _ in input]
                )

    monkeypatch.setattr(embeddings, "_hosted_client", lambda: FakeClient)
    out = embeddings.encode([f"t{i}" for i in range(250)])
    assert len(out) == 250
    assert sizes == [100, 100, 50], "lotes no teto de HOSTED_BATCH_MAX"

    class ShortClient:
        class embeddings:  # noqa: N801
            @staticmethod
            def create(model, input):
                from unittest.mock import MagicMock

                return MagicMock(data=[MagicMock(embedding=[0.1] * 1024)])

    monkeypatch.setattr(embeddings, "_hosted_client", lambda: ShortClient)
    with pytest.raises(RuntimeError, match="2 textos"):
        embeddings.encode(["a", "b"])


def test_hosted_lane_names_the_missing_key(monkeypatch):
    import pytest

    from src.ingestion import embeddings

    monkeypatch.setattr(embeddings.settings, "embedding_provider", "novita")
    monkeypatch.setattr(embeddings.settings, "novita_api_key", None)
    with pytest.raises(ValueError, match="NOVITA_API_KEY"):
        embeddings.encode(["a"])

    monkeypatch.setattr(embeddings.settings, "embedding_provider", "bogus")
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        embeddings.encode(["a"])
