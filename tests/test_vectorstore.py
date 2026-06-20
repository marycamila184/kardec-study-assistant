import pytest
from src.ingestion.vectorstore import VectorStore

_META = {
    "book": "O Livro dos Espíritos",
    "part": "",
    "chapter": "",
    "chapter_title": "Da Encarnação",
    "item_number": "132",
    "subchunk_index": 1,
    "total_subchunks": 1,
}


@pytest.fixture
def store(tmp_path):
    return VectorStore(str(tmp_path), "test_col")


def test_upsert_and_query_returns_document(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["alma e reencarnação"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert len(results) == 1
    assert results[0]["content"] == "alma e reencarnação"


def test_query_returns_low_distance_for_same_vector(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["alma e reencarnação"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert results[0]["distance"] < 0.01  # identical vectors → cosine distance ~0


def test_query_returns_metadata(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["texto"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert results[0]["metadata"]["book"] == "O Livro dos Espíritos"
    assert results[0]["metadata"]["item_number"] == "132"


def test_upsert_is_idempotent(store):
    for _ in range(2):
        store.upsert(
            ids=["doc1"],
            embeddings=[[1.0, 0.0, 0.0]],
            documents=["texto"],
            metadatas=[_META],
        )
    results = store.query([1.0, 0.0, 0.0], n_results=5)
    assert len(results) == 1  # not duplicated
