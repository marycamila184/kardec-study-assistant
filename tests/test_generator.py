import logging
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
    monkeypatch.setattr("src.rag.generator.get_client", lambda: client)
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


def test_generate_masks_placeholder_item_number_in_sources(monkeypatch, mock_client):
    chunks = [
        {
            "content": "Trecho introdutório sem item numerado.",
            "metadata": {
                "book": "O Livro dos Espíritos",
                "chapter_title": "Introdução",
                "item_number": "section-3",
            },
            "distance": 0.4,
        }
    ]
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: chunks)
    result = generate("O que é reencarnação?", [])
    assert result["sources"][0]["item_number"] is None


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
    with patch(
        "src.rag.generator.condense_query", return_value="consulta condensada"
    ) as mock_cond:
        generate("E o que mais ele diz?", history)
    mock_cond.assert_called_once()


def test_generate_skips_condenser_without_history(mock_retrieve, mock_client):
    with patch("src.rag.generator.condense_query") as mock_cond:
        generate("O que é reencarnação?", [])
    mock_cond.assert_not_called()


def test_generate_sources_include_excerpt(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert (
        result["sources"][0]["excerpt"]
        == "A encarnação tem por fim fazê-los progredir."
    )


def test_generate_sets_generation_failed_on_llm_error(mock_retrieve, monkeypatch):
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("API error")
    monkeypatch.setattr("src.rag.generator.get_client", lambda: client)

    result = generate("O que é reencarnação?", [])

    assert result["generation_failed"] is True
    assert result["not_found"] is False
    assert result["sources"] == []


def test_generate_sets_generation_failed_on_retrieval_error(monkeypatch, mock_client):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve", _raise)

    result = generate("O que é reencarnação?", [])

    assert result["generation_failed"] is True
    assert result["not_found"] is False
    assert result["sources"] == []
    mock_client.chat.completions.create.assert_not_called()


def test_generate_falls_back_to_raw_question_when_condenser_fails(
    mock_retrieve, mock_client
):
    history = [{"role": "user", "content": "pergunta anterior"}]
    with patch(
        "src.rag.generator.condense_query", side_effect=RuntimeError("condenser down")
    ):
        result = generate("O que é reencarnação?", history)

    assert result["generation_failed"] is False
    assert result["answer"] == "Resposta gerada."


def test_generate_adds_caveat_for_clinical_keywords(mock_retrieve, mock_client):
    generate("escuto vozes à noite", [])
    system_arg = mock_client.chat.completions.create.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "profissional de saúde" in system_arg


def test_generate_no_caveat_for_normal_question(mock_retrieve, mock_client):
    generate("O que é reencarnação?", [])
    system_arg = mock_client.chat.completions.create.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "profissional de saúde" not in system_arg


def test_generate_logs_on_retrieval_error(monkeypatch, mock_client, caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve", _raise)
    with caplog.at_level(logging.ERROR, logger="src.rag.generator"):
        generate("pergunta", [])
    assert any("retriev" in r.message.lower() for r in caplog.records)
