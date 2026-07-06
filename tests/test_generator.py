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


def test_generate_appends_crisis_note_for_suicidal_question(mock_retrieve, mock_client):
    result = generate("penso em suicídio, o que a doutrina diz?", [])
    assert result["answer"].startswith("Resposta gerada.")
    assert "CVV" in result["answer"]
    assert "188" in result["answer"]


def test_generate_no_crisis_note_for_normal_question(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert "CVV" not in result["answer"]


def test_generate_crisis_note_present_even_when_not_found(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [])
    result = generate("quero morrer, existe perdão?", [])
    assert result["not_found"] is True
    assert "CVV" in result["answer"]


_ITEM_132_CHUNKS = [
    {
        "content": "132. Qual o objetivo da encarnação dos Espíritos?",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
        "footnote_context": "",
    }
]

_OTHER_CHUNKS = [
    {
        "content": "Trecho semanticamente próximo, mas de outro item.",
        "metadata": {
            "book": "A Gênese",
            "chapter_title": "Caracteres da Revelação",
            "item_number": "29",
        },
        "distance": 0.4,
    }
]


def test_generate_direct_item_lookup_leads_sources(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _OTHER_CHUNKS)
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item", lambda b, n: _ITEM_132_CHUNKS
    )
    result = generate("explique a questão 132 do livro dos espíritos", [])
    assert result["not_found"] is False
    assert result["sources"][0]["item_number"] == "132"
    assert result["sources"][0]["book"] == "O Livro dos Espíritos"
    assert len(result["sources"]) == 2


def test_generate_direct_item_lookup_dedupes_semantic_hit(monkeypatch, mock_client):
    monkeypatch.setattr(
        "src.rag.generator.retrieve", lambda q, **kw: _ITEM_132_CHUNKS + _OTHER_CHUNKS
    )
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item", lambda b, n: _ITEM_132_CHUNKS
    )
    result = generate("explique a questão 132 do livro dos espíritos", [])
    item_keys = [(s["book"], s["item_number"]) for s in result["sources"]]
    assert item_keys.count(("O Livro dos Espíritos", "132")) == 1


def test_generate_no_direct_lookup_without_book(
    mock_retrieve, mock_client, monkeypatch
):
    # "item N" (unlike "questão N") implies no book, so no direct lookup
    calls = []
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item",
        lambda b, n: calls.append((b, n)) or [],
    )
    generate("explique o item 132", [])
    assert calls == []


def test_generate_direct_lookup_uses_book_filter_as_book(
    mock_retrieve, mock_client, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item",
        lambda b, n: calls.append((b, n)) or _ITEM_132_CHUNKS,
    )
    generate("explique o item 132", [], book_filter="O Livro dos Espíritos")
    assert calls == [("O Livro dos Espíritos", "132")]


def test_generate_direct_lookup_questao_defaults_to_livro_espiritos(
    monkeypatch, mock_client
):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _OTHER_CHUNKS)
    calls = []
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item",
        lambda b, n: calls.append((b, n)) or _ITEM_132_CHUNKS,
    )
    result = generate("explique a questao 132", [])
    assert calls == [("O Livro dos Espíritos", "132")]
    assert result["sources"][0]["item_number"] == "132"


def test_generate_direct_lookup_failure_falls_back_to_semantic(
    mock_retrieve, mock_client, monkeypatch
):
    def _raise(b, n):
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve_by_item", _raise)
    result = generate("explique a questão 132 do livro dos espíritos", [])
    assert result["generation_failed"] is False
    assert result["answer"] == "Resposta gerada."


def test_generate_answers_from_direct_lookup_when_semantic_empty(
    monkeypatch, mock_client
):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [])
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item", lambda b, n: _ITEM_132_CHUNKS
    )
    result = generate("explique a questão 132 do livro dos espíritos", [])
    assert result["not_found"] is False
    assert result["answer"] == "Resposta gerada."
    assert result["sources"][0]["item_number"] == "132"


def test_generate_answers_from_direct_lookup_when_semantic_raises(
    monkeypatch, mock_client
):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve", _raise)
    monkeypatch.setattr(
        "src.rag.generator.retrieve_by_item", lambda b, n: _ITEM_132_CHUNKS
    )
    result = generate("explique a questão 132 do livro dos espíritos", [])
    assert result["generation_failed"] is False
    assert result["sources"][0]["item_number"] == "132"


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


def _make_client(monkeypatch, content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.generator.get_client", lambda: client)
    return client


_TWO_CHUNKS = [
    {
        "content": "A encarnação tem por fim fazê-los progredir.",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
        "distance": 0.4,
    },
    {
        "content": "O amor resume toda a doutrina.",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter_title": "Amai-vos",
            "item_number": "5",
        },
        "distance": 0.5,
    },
]


def test_generate_fontes_marker_filters_sources_and_is_stripped(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta fundamentada.\n\n[FONTES: 2]")
    result = generate("O que é o amor?", [])
    assert result["answer"] == "Resposta fundamentada."
    assert len(result["sources"]) == 1
    assert result["sources"][0]["item_number"] == "5"


def test_generate_empty_fontes_marker_yields_no_sources(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Não há informação suficiente.\n[FONTES:]")
    result = generate("Pergunta fora das obras", [])
    assert result["answer"] == "Não há informação suficiente."
    assert result["sources"] == []


def test_generate_missing_fontes_marker_keeps_all_sources(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta sem marcador.")
    result = generate("O que é o amor?", [])
    assert len(result["sources"]) == 2


def test_generate_invalid_fontes_indices_keep_all_sources(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta.\n[FONTES: 7, 9]")
    result = generate("O que é o amor?", [])
    assert result["answer"] == "Resposta."
    assert len(result["sources"]) == 2


def test_generate_logs_condenser_failure(mock_retrieve, mock_client, caplog):
    history = [{"role": "user", "content": "pergunta anterior"}]
    with (
        patch("src.rag.generator.condense_query", side_effect=RuntimeError("down")),
        caplog.at_level(logging.ERROR, logger="src.rag.generator"),
    ):
        generate("O que é reencarnação?", history)
    assert any("condense" in r.message.lower() for r in caplog.records)


def test_generate_sources_include_chapter_ref(monkeypatch, mock_client):
    chunks = [
        {
            "content": "132. Qual o objetivo da encarnação dos Espíritos?",
            "metadata": {
                "book": "O Livro dos Espíritos",
                "chapter": "CAPÍTULO II",
                "chapter_title": "DA ENCARNAÇÃO DOS ESPÍRITOS",
                "item_number": "132",
            },
            "distance": 0.4,
        }
    ]
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: chunks)
    result = generate("O que é encarnação?", [])
    assert result["sources"][0]["chapter_ref"] == "CAPÍTULO II"
    assert result["sources"][0]["chapter"] == "DA ENCARNAÇÃO DOS ESPÍRITOS"


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


def test_generate_logs_on_book_fallback_retrieve_error(
    monkeypatch, mock_client, caplog
):
    # First retrieve (book-filtered) returns nothing -> triggers the book_filter
    # fallback; the fallback retrieve then raises and must be logged, not swallowed.
    calls = {"n": 0}

    def _retrieve(query, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve", _retrieve)
    with caplog.at_level(logging.ERROR, logger="src.rag.generator"):
        generate("pergunta", [], book_filter="O Livro dos Espíritos")
    assert any("fallback" in r.message.lower() for r in caplog.records)
