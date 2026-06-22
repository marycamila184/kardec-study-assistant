from unittest.mock import MagicMock, patch

from src.rag.evangelho import get_daily_passage

_CHUNK_1 = {
    "content": "Bem-aventurados os puros de coração.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Bem-aventuranças",
        "item_number": "section-4",
        "subchunk_index": 1,
        "total_subchunks": 1,
    },
    "distance": 0.0,
}

_CHUNK_2 = {
    "content": "Amai-vos uns aos outros.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Amor ao próximo",
        "item_number": "section-7",
        "subchunk_index": 1,
        "total_subchunks": 2,
    },
    "distance": 0.0,
}


def _mock_store(chunks):
    store = MagicMock()
    store.get_by_filter.return_value = chunks
    return store


def test_returns_none_when_no_chunks():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([])):
        result = get_daily_passage()
    assert result is None


def test_returns_passage_with_correct_shape():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result is not None
    assert "date" in result
    assert "content" in result
    assert "source" in result


def test_content_comes_from_selected_chunk():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["content"] == "Bem-aventurados os puros de coração."


def test_source_fields_populated_from_chunk_metadata():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["source"]["book"] == "O Evangelho segundo o Espiritismo"
    assert result["source"]["chapter_title"] == "Bem-aventuranças"
    assert result["source"]["item_number"] == "section-4"
    assert result["source"]["subchunk_index"] == 1
    assert result["source"]["total_subchunks"] == 1


def test_same_date_returns_same_passage():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1, _CHUNK_2])):
        result1 = get_daily_passage()
        result2 = get_daily_passage()
    assert result1["content"] == result2["content"]


def test_date_field_is_today_isoformat():
    import datetime

    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["date"] == datetime.date.today().isoformat()
