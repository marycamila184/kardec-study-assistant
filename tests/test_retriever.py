from unittest.mock import MagicMock

import pytest

from src.rag.retriever import has_real_item_number, retrieve, retrieve_by_item

_MOCK_RESULTS = [
    {
        "content": "alma espírita",
        "metadata": {"book": "X", "chapter_title": "A", "item_number": "1"},
        "distance": 0.5,
    },
    {
        "content": "texto irrelevante",
        "metadata": {"book": "Y", "chapter_title": "B", "item_number": "2"},
        "distance": 1.5,
    },
]


@pytest.fixture(autouse=True)
def mock_deps(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = _MOCK_RESULTS
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    monkeypatch.setattr("src.rag.retriever.encode", lambda texts: [[0.1] * 1024])


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
        {
            "$and": [
                {"book": {"$eq": "O Livro dos Espíritos"}},
                {"item_number": {"$eq": "1"}},
            ]
        }
    )


def test_retrieve_by_item_returns_empty_list_when_not_found(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = []
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "999")
    assert results == []


def test_retrieve_by_item_with_chapter_adds_chapter_to_filter(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [_MOCK_RESULTS[0]]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    retrieve_by_item("O Evangelho Segundo o Espiritismo", "1", chapter="CAPÍTULO IV")
    mock_store.get_by_filter.assert_called_once_with(
        {
            "$and": [
                {"book": {"$eq": "O Evangelho Segundo o Espiritismo"}},
                {"item_number": {"$eq": "1"}},
                {"chapter": {"$eq": "CAPÍTULO IV"}},
            ]
        }
    )


def test_split_footnotes_separates_clean_content_from_notes():
    from src.rag.retriever import _split_footnotes

    content = "Texto principal.\n[Nota 1] Primeira nota.\n[Nota 2] Segunda nota."
    clean, footnotes = _split_footnotes(content)
    assert clean == "Texto principal."
    assert footnotes == "[Nota 1] Primeira nota.\n[Nota 2] Segunda nota."


def test_split_footnotes_returns_unchanged_when_no_marker():
    from src.rag.retriever import _split_footnotes

    clean, footnotes = _split_footnotes("Texto sem notas.")
    assert clean == "Texto sem notas."
    assert footnotes == ""


def test_retrieve_strips_footnote_suffix_from_content(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {
            "content": "Texto principal.\n[Nota 1] Nota explicativa.",
            "metadata": {},
            "distance": 0.5,
        },
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve("alma")
    assert results[0]["content"] == "Texto principal."
    assert results[0]["footnote_context"] == "[Nota 1] Nota explicativa."


def test_retrieve_footnote_context_empty_when_no_footnote(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"content": "Texto sem notas.", "metadata": {}, "distance": 0.5},
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve("alma")
    assert results[0]["footnote_context"] == ""


def test_retrieve_by_item_strips_footnote_suffix(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [
        {
            "content": "Item principal.\n[Nota 1] Explicação.",
            "metadata": {},
            "distance": 0.0,
        },
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "1")
    assert results[0]["content"] == "Item principal."
    assert results[0]["footnote_context"] == "[Nota 1] Explicação."


def test_has_real_item_number_true_for_numbered_item():
    assert has_real_item_number("132") is True


def test_has_real_item_number_false_for_placeholder():
    assert has_real_item_number("section-3") is False


def test_has_real_item_number_false_for_none_or_empty():
    assert has_real_item_number(None) is False
    assert has_real_item_number("") is False


from src.rag.retriever import (
    EVANGELHO_BOOK,
    chapter_commentary,
    retrieve_by_chapter,
)

_EV = "O Evangelho Segundo o Espiritismo"


def _ev_chunk(item, content, sub=0):
    return {
        "content": content,
        "metadata": {
            "book": _EV,
            "chapter": "CAPÍTULO XX",
            "item_number": item,
            "subchunk_index": sub,
        },
        "distance": 0.0,
    }


def test_retrieve_by_chapter_filters_and_orders(monkeypatch):
    mock_store = MagicMock()
    # returned out of order; expect (item asc, subchunk asc)
    mock_store.get_by_filter.return_value = [
        _ev_chunk("2", "comentario dois"),
        _ev_chunk("1", "verso b", sub=1),
        _ev_chunk("1", "verso a", sub=0),
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_chapter(_EV, "CAPÍTULO XX")
    assert [r["content"] for r in results] == ["verso a", "verso b", "comentario dois"]
    mock_store.get_by_filter.assert_called_once_with(
        {"$and": [{"book": {"$eq": _EV}}, {"chapter": {"$eq": "CAPÍTULO XX"}}]}
    )
    # footnotes stripped -> footnote_context key present
    assert all("footnote_context" in r for r in results)


def test_chapter_commentary_excludes_studied_item(monkeypatch):
    monkeypatch.setattr(
        "src.rag.retriever.retrieve_by_chapter",
        lambda b, c: [_ev_chunk("1", "verso"), _ev_chunk("2", "comentario")],
    )
    out = chapter_commentary(_EV, "CAPÍTULO XX", "1")
    assert [r["content"] for r in out] == ["comentario"]


def test_chapter_commentary_respects_char_cap(monkeypatch):
    monkeypatch.setattr(
        "src.rag.retriever.retrieve_by_chapter",
        lambda b, c: [
            _ev_chunk("2", "a" * 2500),
            _ev_chunk("3", "b" * 2500),
            _ev_chunk("4", "c" * 2500),
        ],
    )
    out = chapter_commentary(_EV, "CAPÍTULO XX", "1", char_cap=3000)
    # first sibling always included; stop before exceeding the cap
    assert [r["content"][0] for r in out] == ["a"]


def test_chapter_commentary_always_returns_first_sibling(monkeypatch):
    monkeypatch.setattr(
        "src.rag.retriever.retrieve_by_chapter",
        lambda b, c: [_ev_chunk("2", "x" * 9000)],
    )
    out = chapter_commentary(_EV, "CAPÍTULO XX", "1", char_cap=3000)
    assert len(out) == 1  # a single over-cap sibling is never dropped to empty


def test_chapter_commentary_non_evangelho_returns_empty():
    assert chapter_commentary("O Livro dos Espíritos", "CAP I", "1") == []


def test_chapter_commentary_empty_chapter_returns_empty():
    assert chapter_commentary(_EV, "", "1") == []
