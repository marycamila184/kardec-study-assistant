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
