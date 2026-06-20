from unittest.mock import MagicMock

import pytest

from src.rag.retriever import retrieve

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
