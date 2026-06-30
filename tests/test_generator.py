from unittest.mock import MagicMock, patch

import pytest

from src.rag.generator import generate

_CHUNKS = [
    {
        "content": "A encarnação tem por fim fazê-los progredir.",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
        "distance": 0.4,
    }
]


@pytest.fixture
def mock_retrieve(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)


@pytest.fixture
def mock_client(monkeypatch):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Resposta gerada."))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.generator._get_client", lambda: client)
    return client


def test_generate_returns_answer(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert result["answer"] == "Resposta gerada."
    assert result["not_found"] is False


def test_generate_returns_deduplicated_sources(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert len(result["sources"]) == 1
    assert result["sources"][0]["book"] == "O Livro dos Espíritos"
    assert result["sources"][0]["item_number"] == "132"


def test_generate_not_found_when_no_chunks(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [])
    result = generate("Fale sobre budismo", [])
    assert result["not_found"] is True
    assert result["sources"] == []
    mock_client.chat.completions.create.assert_not_called()


def test_generate_calls_condenser_when_history_present(mock_retrieve, mock_client):
    history = [
        {"role": "user", "content": "O que é reencarnação?"},
        {"role": "assistant", "content": "É o retorno do espírito."},
    ]
    with patch("src.rag.generator.condense_query", return_value="consulta condensada") as mock_cond:
        generate("E o que mais ele diz?", history)
    mock_cond.assert_called_once()


def test_generate_skips_condenser_without_history(mock_retrieve, mock_client):
    with patch("src.rag.generator.condense_query") as mock_cond:
        generate("O que é reencarnação?", [])
    mock_cond.assert_not_called()


def test_generate_sources_include_excerpt(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert result["sources"][0]["excerpt"] == "A encarnação tem por fim fazê-los progredir."
