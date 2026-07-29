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


def _graded_encoder():
    """Four chunks at cosines 1.00, 0.95, 0.80 and 0.60 to the answer."""
    import math

    def vec(cos):
        return [cos, math.sqrt(1 - cos * cos)]

    return _stub_encoder(
        {
            "r": [1.0, 0.0],
            "top": vec(1.00),
            "perto": vec(0.95),
            "medio": vec(0.80),
            "longe": vec(0.60),
        }
    )


def test_per_chunk_similarities_returns_one_value_per_chunk_in_order():
    from src.rag.groundedness import per_chunk_similarities

    enc = _stub_encoder({"r": [1.0, 0.0], "a": [1.0, 0.0], "b": [0.0, 1.0]})
    assert per_chunk_similarities("r", _chunks("a", "b"), encoder=enc) == [1.0, 0.0]


def test_per_chunk_similarities_empty_when_no_chunks():
    from src.rag.groundedness import per_chunk_similarities

    assert per_chunk_similarities("r", [], encoder=_stub_encoder({})) == []


def test_per_chunk_similarities_empty_when_answer_blank():
    from src.rag.groundedness import per_chunk_similarities

    assert per_chunk_similarities("   ", _chunks("a"), encoder=_stub_encoder({})) == []
