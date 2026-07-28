import logging
from unittest.mock import MagicMock, patch

import pytest

from src.rag.generator import NOT_FOUND_MESSAGE, generate

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
    monkeypatch.setattr("src.rag.prose.get_client", lambda role="json": client)
    return client


@pytest.fixture(autouse=True)
def _default_sensitivity_normal(monkeypatch):
    # Default every test to the "normal" tier; sensitivity-specific tests
    # override this. Keeps existing tests off the network (classify_sensitivity
    # would otherwise call the real client) and on the pre-tiering behavior.
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "normal")


def test_generate_smalltalk_short_circuits_without_retrieval_or_llm(monkeypatch):
    # A pure acknowledgment must skip retrieval and the LLM entirely and return
    # a warm reply with no source chips or suggestions.
    def _boom(*args, **kwargs):
        raise AssertionError("retrieval/LLM should not run for small talk")

    monkeypatch.setattr("src.rag.generator.retrieve", _boom)
    monkeypatch.setattr("src.rag.prose.get_client", _boom)

    from src.rag.generator import SMALLTALK_REPLIES

    result = generate("entendi obrigada", [])
    assert result["answer"] in SMALLTALK_REPLIES
    assert result["sources"] == []
    assert result["suggested_questions"] == []
    assert result["not_found"] is False
    assert result["generation_failed"] is False


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


def test_generate_no_crisis_note_for_normal_question(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert "CVV" not in result["answer"]


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
    monkeypatch.setattr("src.rag.prose.get_client", lambda role="json": client)
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


def test_generate_malformed_fontes_marker_is_stripped(monkeypatch):
    # The model sometimes mangles the trailer (e.g. "/FONTES:" with no brackets);
    # it must still be stripped, not leaked into the answer, and an empty body
    # means no sources.
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "As passagens não cobrem isso.\n\n/FONTES:")
    result = generate("Pergunta fora das obras", [])
    assert result["answer"] == "As passagens não cobrem isso."
    assert result["sources"] == []


def test_generate_fontes_marker_without_brackets_is_stripped(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta.\nFONTES: 2")
    result = generate("O que é o amor?", [])
    assert result["answer"] == "Resposta."
    assert len(result["sources"]) == 1
    assert result["sources"][0]["item_number"] == "5"


def test_generate_lowercase_fontes_prose_is_not_stripped(monkeypatch):
    # A genuine sentence ending in "fontes:" must never be mistaken for the marker.
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Consulte as fontes: as obras de Kardec.")
    result = generate("O que é o amor?", [])
    assert result["answer"] == "Consulte as fontes: as obras de Kardec."


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


def test_generate_parses_seguir_marker_into_suggested_questions(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(
        monkeypatch,
        "Resposta.\n[FONTES: 1]\n[SEGUIR: O que é o perispírito? | Como ocorre a reencarnação?]",
    )
    result = generate("O que é a alma?", [])
    assert result["answer"] == "Resposta."
    assert result["suggested_questions"] == [
        "O que é o perispírito?",
        "Como ocorre a reencarnação?",
    ]
    assert len(result["sources"]) == 1


def test_generate_markers_parsed_in_either_order(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta.\n[SEGUIR: Pergunta A?]\n[FONTES: 2]")
    result = generate("O que é a alma?", [])
    assert result["answer"] == "Resposta."
    assert result["suggested_questions"] == ["Pergunta A?"]
    assert result["sources"][0]["item_number"] == "5"


def test_generate_seguir_caps_at_two_questions(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta.\n[SEGUIR: A? | B? | C? | D?]")
    result = generate("O que é a alma?", [])
    assert result["suggested_questions"] == ["A?", "B?"]


def test_generate_no_seguir_marker_yields_no_suggestions(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert result["suggested_questions"] == []


def test_generate_crisis_suppresses_suggested_questions(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _TWO_CHUNKS)
    _make_client(monkeypatch, "Resposta.\n[FONTES: 1]\n[SEGUIR: A? | B?]")
    result = generate("penso em suicídio, o que a doutrina diz?", [])
    assert result["suggested_questions"] == []
    assert "CVV" in result["answer"]
    assert "[SEGUIR" not in result["answer"]


def test_generate_not_found_has_no_suggestions(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [])
    result = generate("Fale sobre budismo", [])
    assert result["suggested_questions"] == []


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
    monkeypatch.setattr("src.rag.prose.get_client", lambda role="json": client)

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


def test_generate_blends_anchor_into_retrieval_query(monkeypatch, mock_client):
    captured = {}

    def _capture(query, **kw):
        captured["query"] = query
        return _CHUNKS

    monkeypatch.setattr("src.rag.generator.retrieve", _capture)
    generate("preciso ser criança?", [], anchor_text="passagem sobre humildade")
    assert "passagem sobre humildade" in captured["query"]


def test_generate_no_anchor_leaves_query_clean(monkeypatch, mock_client):
    captured = {}

    def _capture(query, **kw):
        captured["query"] = query
        return _CHUNKS

    monkeypatch.setattr("src.rag.generator.retrieve", _capture)
    generate("o que é humildade?", [], anchor_text=None)
    assert captured["query"] == "o que é humildade?"


from src.rag.generator import _direct_item_chunks


def test_direct_item_chunks_skips_evangelho_without_chapter(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("retrieve_by_item must not run for chapterless Evangelho")

    monkeypatch.setattr("src.rag.generator.retrieve_by_item", _boom)
    # "item 1 do Evangelho" resolves book=Evangelho, no chapter -> ambiguous -> []
    assert _direct_item_chunks("explique o item 1 do Evangelho", None) == []


def test_direct_item_chunks_still_works_for_livro_espiritos(monkeypatch):
    called = {}

    def _mock_retrieve(b, i):
        called["args"] = (b, i)
        return [{"x": 1}]

    monkeypatch.setattr("src.rag.generator.retrieve_by_item", _mock_retrieve)
    out = _direct_item_chunks("questão 132 do Livro dos Espíritos", None)
    assert out == [{"x": 1}]
    assert called["args"] == ("O Livro dos Espíritos", "132")


def test_generate_keyword_crisis_returns_fixed_exit(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("classifier/retrieval must not run on keyword crisis")

    monkeypatch.setattr("src.rag.generator.classify_sensitivity", _boom)
    monkeypatch.setattr("src.rag.generator.retrieve", _boom)
    result = generate("eu não aguento mais viver", [])
    assert result["safety_level"] == "crise"
    assert "188" in result["answer"]
    assert result["sources"] == []
    assert result["suggested_questions"] == []


def test_generate_llm_crise_returns_fixed_exit(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "crise")
    result = generate("estou muito mal", [])
    assert result["safety_level"] == "crise"
    assert "188" in result["answer"]
    assert result["sources"] == []


def test_generate_abalo_filters_dark_chunks_and_suppresses_chips(
    monkeypatch, mock_client
):
    dark = {
        "content": "relato de suicida",
        "metadata": {
            "book": "O Céu e o Inferno",
            "chapter_title": "SUICIDAS",
            "item_number": "1",
        },
    }
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [dark] + _CHUNKS)
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "abalo")
    result = generate("estou cansada e não aguento mais", [])
    assert result["safety_level"] == "abalo"
    assert all(s["excerpt"] != "relato de suicida" for s in result["sources"])
    assert result["suggested_questions"] == []


def test_generate_normal_unchanged(monkeypatch, mock_client):
    captured = {}

    def _capture(
        question, chunks, history, mht, add_caveat=False, sensitive=False, **kw
    ):
        captured["sensitive"] = sensitive
        return "SYS", [{"role": "user", "content": question}]

    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)
    monkeypatch.setattr("src.rag.generator.classify_sensitivity", lambda t: "normal")
    monkeypatch.setattr("src.rag.generator.build_messages", _capture)
    result = generate("o que é o perispírito?", [])
    assert result["safety_level"] == "normal"
    assert captured["sensitive"] is False


def test_generate_enriches_evangelho_top_hit(monkeypatch, mock_client):
    ev = {
        "content": "verso da parábola",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter": "CAPÍTULO XX",
            "chapter_title": "OS TRABALHADORES",
            "item_number": "1",
        },
    }
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [ev])

    def _spy_append(passages):
        passages.append(
            {
                "content": "comentario kardec",
                "metadata": {
                    "book": "O Evangelho Segundo o Espiritismo",
                    "chapter_title": "OS TRABALHADORES",
                    "item_number": "2",
                },
            }
        )
        return passages

    monkeypatch.setattr("src.rag.generator.append_chapter_commentary", _spy_append)
    result = generate("o que significa a parábola?", [])
    excerpts = [s["excerpt"] for s in result["sources"]]
    assert "comentario kardec" in excerpts


def test_generate_topic_suicide_answers_with_crisis_note(mock_retrieve, mock_client):
    # A doctrinal question about suicide gets a real grounded answer — not the
    # fixed exit — but the CVV note is appended deterministically in code.
    from src.rag.crisis import CRISIS_NOTE

    result = generate("O que Kardec diz sobre o suicídio?", [])
    assert result["generation_failed"] is False
    assert result["answer"] != ""
    assert result["answer"].endswith(CRISIS_NOTE)
    assert result["safety_level"] == "normal"  # no forced escalation


def test_generate_first_person_ideation_still_fixed_exit(monkeypatch):
    from src.rag.crisis import CRISIS_EXIT_MESSAGE

    def _boom(*args, **kwargs):
        raise AssertionError("retrieval/LLM must not run on crisis exit")

    monkeypatch.setattr("src.rag.generator.retrieve", _boom)
    monkeypatch.setattr("src.rag.prose.get_client", _boom)
    result = generate("penso em suicídio", [])
    assert result["answer"] == CRISIS_EXIT_MESSAGE
    assert result["safety_level"] == "crise"


def test_chat_answer_goes_through_the_prose_lane(monkeypatch):
    """The /chat generation call must use prose_completion, not get_client
    directly, so PROSE_PROVIDER routes it."""
    import src.rag.generator as gen

    monkeypatch.setattr(
        gen,
        "retrieve",
        lambda *a, **k: [
            {
                "metadata": {
                    "book": "O Livro dos Espíritos",
                    "item_number": "625",
                    "chapter_title": "Cap",
                    "chapter": "CAPÍTULO I",
                },
                "content": "trecho",
                "footnote_context": "",
            }
        ],
    )
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    called = {}

    def _fake_prose(system, messages, max_tokens=1024):
        called["hit"] = True
        return "Resposta grounded.\n[FONTES: 1]\n[SEGUIR: a | b]"

    monkeypatch.setattr(gen, "prose_completion", _fake_prose)

    out = gen.generate("o que é o espírito?", [])
    assert called["hit"] is True
    assert out["answer"] == "Resposta grounded."
    assert out["suggested_questions"] == ["a", "b"]


def test_chat_answer_never_ends_with_a_question(monkeypatch):
    import src.rag.generator as gen

    monkeypatch.setattr(
        gen,
        "retrieve",
        lambda *a, **k: [
            {
                "metadata": {
                    "book": "O Livro dos Espíritos",
                    "item_number": "625",
                    "chapter_title": "Cap",
                    "chapter": "CAPÍTULO I",
                },
                "content": "trecho",
                "footnote_context": "",
            }
        ],
    )
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    monkeypatch.setattr(gen, "attribute_sources", lambda answer, cs, **k: cs)
    monkeypatch.setattr(
        gen,
        "prose_completion",
        lambda *a, **k: "A alma persiste. O que você acha disso?",
    )

    out = gen.generate("a alma persiste?", [])
    assert out["answer"] == "A alma persiste."


def test_chat_strips_model_written_citations(monkeypatch):
    """Model-written citations must not compete with the real source chips."""
    import src.rag.generator as gen

    monkeypatch.setattr(
        gen,
        "retrieve",
        lambda *a, **k: [
            {
                "metadata": {
                    "book": "O Livro dos Espíritos",
                    "item_number": "625",
                    "chapter_title": "Cap",
                    "chapter": "CAPÍTULO I",
                },
                "content": "trecho",
                "footnote_context": "",
            }
        ],
    )
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    monkeypatch.setattr(gen, "attribute_sources", lambda answer, cs, **k: cs)
    monkeypatch.setattr(
        gen,
        "prose_completion",
        lambda *a, **k: "A alma persiste (O Livro dos Espíritos, questão 625).",
    )

    out = gen.generate("a alma persiste?", [])
    assert "questão 625" not in out["answer"]
    assert out["answer"] == "A alma persiste."


def test_prose_lane_attributes_sources_from_the_vector_store(monkeypatch):
    """On the prose lane the model's [FONTES:] marker is ignored entirely —
    chips come from answer-to-chunk similarity computed in code."""
    import src.rag.generator as gen

    chunks = [
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "usado",
            "footnote_context": "",
        },
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "886",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "ignorado",
            "footnote_context": "",
        },
    ]
    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(chunks))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    # The model names a passage index that does not exist; it must not matter.
    monkeypatch.setattr(
        gen, "prose_completion", lambda *a, **k: "A alma persiste.\n[FONTES: 625]"
    )
    monkeypatch.setattr(gen, "attribute_sources", lambda answer, cs, **k: [cs[0]])

    out = gen.generate("a alma persiste?", [])
    assert [s["item_number"] for s in out["sources"]] == ["625"]


def test_prose_lane_empty_after_citation_strip_is_generation_failed(monkeypatch):
    """Finding 1: if strip_model_citations consumes the entire answer, the
    empty result must not be returned as a success — it must degrade to the
    same failure path as an LLM error."""
    import src.rag.generator as gen

    chunks = [
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "trecho",
            "footnote_context": "",
        }
    ]
    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(chunks))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    monkeypatch.setattr(
        gen,
        "prose_completion",
        lambda *a, **k: "(O Livro dos Espíritos, questão 625)",
    )

    out = gen.generate("a alma persiste?", [])
    assert out["generation_failed"] is True
    assert out["answer"] == gen.GENERATION_FAILED_MESSAGE
    assert out["sources"] == []
    assert out["suggested_questions"] == []


def test_prose_lane_attribute_sources_failure_falls_back_to_marker_chunks(
    monkeypatch,
):
    """Finding 2: attribute_sources runs the real bge-m3 encoder in production
    and can fail (e.g. OOM). A perfectly good answer must survive, falling
    back to the chunks the [FONTES:] marker resolved."""
    import src.rag.generator as gen

    chunks = [
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "trecho",
            "footnote_context": "",
        }
    ]
    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(chunks))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    monkeypatch.setattr(
        gen,
        "prose_completion",
        lambda *a, **k: "Uma resposta perfeitamente boa.\n[FONTES: 1]",
    )

    def _boom(answer, cs, **k):
        raise RuntimeError("embedding model OOM")

    monkeypatch.setattr(gen, "attribute_sources", _boom)

    out = gen.generate("a alma persiste?", [])
    assert out["generation_failed"] is False
    assert out["answer"] == "Uma resposta perfeitamente boa."
    assert len(out["sources"]) == 1
    assert out["sources"][0]["item_number"] == "625"


def test_monitor_failure_never_fails_a_request_on_frozen_lane(monkeypatch):
    """Finding 3: counts_personification (and friends) are log-only monitors;
    even with PROSE_PROVIDER unset, a monitor raising must not turn a good
    answer into a generation failure."""
    import src.rag.generator as gen

    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(_CHUNKS))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", None)

    def _boom(*a, **k):
        raise RuntimeError("monitor exploded")

    monkeypatch.setattr(gen, "counts_personification", _boom)

    def _fake_prose(system, messages, max_tokens=1024):
        return "Resposta gerada."

    monkeypatch.setattr(gen, "prose_completion", _fake_prose)

    out = gen.generate("o que é o espírito?", [])
    assert out["generation_failed"] is False
    assert out["answer"] == "Resposta gerada."


def test_prose_lane_strips_leaked_marker_debris(monkeypatch):
    """Live A/B evidence: riv-ai-v2 emits [FONTES:] mid-text with emoji
    decoration, which the end-anchored strip_trailing_markers cannot catch.
    The debris pass must remove it before display."""
    import src.rag.generator as gen

    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(_CHUNKS))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", "ollama")
    monkeypatch.setattr(
        gen,
        "prose_completion",
        lambda *a, **k: "A lei é clara.\n\n📖 [FONTES: O Livro dos Espíritos, 633]\n👉",
    )
    monkeypatch.setattr(gen, "attribute_sources", lambda answer, cs, **k: cs)

    out = gen.generate("qual a lei?", [])
    assert out["answer"] == "A lei é clara."


def test_marker_lane_still_filters_by_fontes(monkeypatch):
    """With PROSE_PROVIDER unset the current provider honors [FONTES:], so
    today's behavior must be preserved exactly."""
    import src.rag.generator as gen

    chunks = [
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "a",
            "footnote_context": "",
        },
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "item_number": "886",
                "chapter_title": "Cap",
                "chapter": "CAPÍTULO I",
            },
            "content": "b",
            "footnote_context": "",
        },
    ]
    monkeypatch.setattr(gen, "retrieve", lambda *a, **k: list(chunks))
    monkeypatch.setattr(gen, "classify_sensitivity", lambda *a, **k: "normal")
    monkeypatch.setattr(gen.settings, "prose_provider", None)
    monkeypatch.setattr(
        gen, "prose_completion", lambda *a, **k: "Resposta.\n[FONTES: 2]"
    )

    out = gen.generate("pergunta?", [])
    assert [s["item_number"] for s in out["sources"]] == ["886"]


# ── Fabricated quotations (found in production 2026-07-28) ──────────────────


def test_a_fabricated_quotation_withholds_the_whole_answer(
    monkeypatch, mock_client, mock_retrieve
):
    """Asked about "duplo etéreo" — not Kardec's vocabulary — the model invented
    a sentence, quoted it and attributed it to Kardec with a chapter and item.
    The answer must not be shown: the same improvisation wrote the paragraphs
    around it."""
    fabricated = (
        "O duplo etéreo é uma extensão do perispírito. "
        'Kardec escreve que "o duplo etéreo é uma espécie de envoltório '
        'fluídico que envolve o corpo físico e o penetra inteiramente" '
        "(A Gênese, capítulo OS FLUIDOS, item 18).[FONTES: 1][SEGUIR:]"
    )
    monkeypatch.setattr(
        "src.rag.generator.prose_completion", lambda s, m, **kw: fabricated
    )
    result = generate("e o duplo etéreo ou aura?", [])

    assert result["answer"] == NOT_FOUND_MESSAGE
    assert result["not_found"] is True
    assert result["sources"] == []
    # Not a crash: the model answered, and what it said cannot be shown.
    assert result["generation_failed"] is False


def test_an_answer_quoting_the_retrieved_text_is_untouched(
    monkeypatch, mock_client, mock_retrieve
):
    grounded = 'Kardec escreve que "' + _CHUNKS[0]["content"] + '".[FONTES: 1][SEGUIR:]'
    monkeypatch.setattr(
        "src.rag.generator.prose_completion", lambda s, m, **kw: grounded
    )
    result = generate("o que é a encarnação?", [])

    assert result["answer"] != NOT_FOUND_MESSAGE
    assert result["not_found"] is False


def test_an_absent_premise_is_corrected_before_the_answer(
    monkeypatch, mock_client, mock_retrieve
):
    """Reported from real use: 'isso influencia o meu ectoplasma' got a
    confident doctrinal answer. The correction comes first — after it, the
    explanation would read as confirming the premise."""
    monkeypatch.setattr(
        "src.rag.generator.prose_completion",
        lambda s, m, **kw: "Uma explicação qualquer.[FONTES: 1][SEGUIR:]",
    )
    monkeypatch.setattr(
        "src.rag.generator.unsupported_terms", lambda q, c: ["ectoplasma"]
    )
    result = generate("isso influencia o meu ectoplasma?", [])

    assert result["answer"].startswith("As obras de Allan Kardec não usam")
    assert "Uma explicação qualquer." in result["answer"]


def test_an_ordinary_question_gets_no_note(monkeypatch, mock_client, mock_retrieve):
    monkeypatch.setattr(
        "src.rag.generator.prose_completion",
        lambda s, m, **kw: "Uma explicação qualquer.[FONTES: 1][SEGUIR:]",
    )
    result = generate("o que é a encarnação?", [])
    assert not result["answer"].startswith("As obras de Allan Kardec não usam")
