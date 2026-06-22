from unittest.mock import MagicMock

import pytest

from src.rag.retriever import retrieve, retrieve_by_item

_MOCK_RESULTS = [
    {"content": "alma espírita", "metadata": {"book": "X", "chapter_title": "A", "item_number": "1"}, "distance": 0.5},
    {"content": "texto irrelevante", "metadata": {"book": "Y", "chapter_title": "B", "item_number": "2"}, "distance": 1.5},
]


@pytest.fixture(autouse=True)
def mock_deps(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = _MOCK_RESULTS
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    monkeypatch.setattr("src.rag.retriever.encode", lambda texts: [[0.1] * 768])


def test_retrieve_filters_chunks_above_max_distance():
    results = retrieve("alma")
    assert len(results) == 1
    assert results[0]["content"] == "alma espírita"


def test_retrieve_keeps_chunks_at_or_below_max_distance():
    results = retrieve("alma")
    assert all(r["distance"] <= 1.2 for r in results)


def test_retrieve_returns_empty_when_all_too_distant(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"content": "irrelevante", "metadata": {}, "distance": 1.9},
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve("budismo")
    assert results == []


def test_retrieve_by_item_calls_get_by_filter_with_correct_where(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [_MOCK_RESULTS[0]]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "1")
    assert len(results) == 1
    mock_store.get_by_filter.assert_called_once_with(
        {"$and": [{"book": {"$eq": "O Livro dos Espíritos"}}, {"item_number": {"$eq": "1"}}]}
    )


def test_retrieve_by_item_returns_empty_list_when_not_found(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = []
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "999")
    assert results == []
