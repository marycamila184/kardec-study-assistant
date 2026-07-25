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
    # margin=1.0 keeps both, so this tests ordering alone rather than the cut.
    out = attribute_sources(
        "r", _chunks("meio", "exato"), min_similarity=0.0, margin=1.0, encoder=enc
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


# --- relative margin --------------------------------------------------------
#
# The 2026-07-25 A/B run showed an absolute threshold cannot separate used
# passages from merely-retrieved ones: the similarity LEVEL is a property of the
# question's vocabulary, not of relevance. The worst chunk for "o que é o
# perispírito?" (0.744) outscored the best chunk for "o que a doutrina diz sobre
# o perdão?" (0.740). At 0.35, 75 of 75 chunks survived. The signal is the step
# between chunks of the SAME question — mean 0.092 at the elbow — so the cut is
# relative to that question's top score.


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


def test_keeps_chunks_within_the_margin_of_the_best():
    from src.rag.groundedness import attribute_sources

    out = attribute_sources(
        "r",
        _chunks("top", "perto", "medio", "longe"),
        margin=0.10,
        min_similarity=0.0,
        encoder=_graded_encoder(),
    )
    assert [c["content"] for c in out] == ["top", "perto"]


def test_margin_adapts_to_a_question_whose_scores_all_sit_low():
    """The same rule on a low-scoring question keeps the same shape — this is
    the whole point of going relative."""
    import math

    from src.rag.groundedness import attribute_sources

    def vec(cos):
        return [cos, math.sqrt(1 - cos * cos)]

    enc = _stub_encoder(
        {"r": [1.0, 0.0], "a": vec(0.60), "b": vec(0.56), "c": vec(0.40)}
    )
    out = attribute_sources(
        "r", _chunks("a", "b", "c"), margin=0.10, min_similarity=0.0, encoder=enc
    )
    assert [c["content"] for c in out] == ["a", "b"]


def test_caps_the_number_of_chips():
    from src.rag.groundedness import attribute_sources

    out = attribute_sources(
        "r",
        _chunks("top", "perto", "medio", "longe"),
        margin=1.0,  # everything is within margin
        max_sources=3,
        min_similarity=0.0,
        encoder=_graded_encoder(),
    )
    assert [c["content"] for c in out] == ["top", "perto", "medio"]


def test_absolute_floor_still_applies_under_the_margin():
    """The margin is relative, so a uniformly terrible retrieval would keep
    everything. The floor is the backstop — and the never-empty guarantee still
    wins over it."""
    from src.rag.groundedness import attribute_sources

    import math

    def vec(cos):
        return [cos, math.sqrt(1 - cos * cos)]

    enc = _stub_encoder({"r": [1.0, 0.0], "a": vec(0.20), "b": vec(0.18)})
    out = attribute_sources(
        "r", _chunks("a", "b"), margin=0.10, min_similarity=0.35, encoder=enc
    )
    assert [c["content"] for c in out] == ["a"]


# --- per_chunk_similarities --------------------------------------------------


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
