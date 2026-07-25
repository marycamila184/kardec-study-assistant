from src.rag.groundedness import groundedness_score


def _chunks(*texts):
    return [{"metadata": {}, "content": t} for t in texts]


def _stub_encoder(vectors):
    """Returns an encoder yielding fixed vectors in call order."""

    def encode(texts):
        return [vectors[t] for t in texts]

    return encode


def test_identical_vectors_score_one():
    enc = _stub_encoder({"resposta": [1.0, 0.0], "trecho": [1.0, 0.0]})
    assert groundedness_score("resposta", _chunks("trecho"), encoder=enc) == 1.0


def test_orthogonal_vectors_score_zero():
    enc = _stub_encoder({"resposta": [1.0, 0.0], "trecho": [0.0, 1.0]})
    assert groundedness_score("resposta", _chunks("trecho"), encoder=enc) == 0.0


def test_averages_across_chunks():
    enc = _stub_encoder({"r": [1.0, 0.0], "a": [1.0, 0.0], "b": [0.0, 1.0]})
    assert groundedness_score("r", _chunks("a", "b"), encoder=enc) == 0.5


def test_empty_chunks_score_zero():
    enc = _stub_encoder({"r": [1.0, 0.0]})
    assert groundedness_score("r", [], encoder=enc) == 0.0


def test_empty_answer_scores_zero():
    enc = _stub_encoder({})
    assert groundedness_score("   ", _chunks("a"), encoder=enc) == 0.0


def test_zero_vector_does_not_divide_by_zero():
    enc = _stub_encoder({"r": [0.0, 0.0], "a": [1.0, 0.0]})
    assert groundedness_score("r", _chunks("a"), encoder=enc) == 0.0


# --- attribute_sources ------------------------------------------------------


def test_keeps_only_chunks_above_the_threshold():
    """Attribution is computed from the vector store, never from the model."""
    from src.rag.groundedness import attribute_sources

    enc = _stub_encoder({"r": [1.0, 0.0], "perto": [1.0, 0.0], "longe": [0.0, 1.0]})
    out = attribute_sources(
        "r", _chunks("perto", "longe"), min_similarity=0.5, encoder=enc
    )
    assert [c["content"] for c in out] == ["perto"]


def test_orders_by_similarity_descending():
    from src.rag.groundedness import attribute_sources

    enc = _stub_encoder(
        {
            "r": [1.0, 0.0],
            "meio": [0.7071, 0.7071],
            "exato": [1.0, 0.0],
        }
    )
    out = attribute_sources(
        "r", _chunks("meio", "exato"), min_similarity=0.0, encoder=enc
    )
    assert [c["content"] for c in out] == ["exato", "meio"]


def test_never_returns_empty_when_chunks_exist():
    """A user must never see an answer with no source at all; the single best
    chunk survives even when nothing clears the threshold."""
    from src.rag.groundedness import attribute_sources

    enc = _stub_encoder({"r": [1.0, 0.0], "a": [0.0, 1.0]})
    out = attribute_sources("r", _chunks("a"), min_similarity=0.9, encoder=enc)
    assert [c["content"] for c in out] == ["a"]


def test_no_chunks_gives_no_sources():
    from src.rag.groundedness import attribute_sources

    assert attribute_sources("r", [], encoder=_stub_encoder({})) == []
