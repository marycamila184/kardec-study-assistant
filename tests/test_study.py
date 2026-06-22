from unittest.mock import MagicMock, patch

import pytest

from src.rag.study import study

_CHUNK = {
    "content": "A alma é imortal.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "150",
        "chapter_title": "Da Alma",
    },
    "distance": 0.0,
}

_LLM_JSON = '{"explanation": "Explicação.", "practical_example": "Exemplo."}'


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_study_returns_none_when_item_not_found():
    with patch("src.rag.study.retrieve_by_item", return_value=[]):
        result = study("O Livro dos Espíritos", "999")
    assert result is None


def test_study_returns_original_text():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["original_text"] == "A alma é imortal."


def test_study_returns_explanation_from_llm():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["explanation"] == "Explicação."
    assert result["practical_example"] == "Exemplo."


def test_study_sets_generation_failed_on_llm_error():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API error")
        result = study("O Livro dos Espíritos", "150")
    assert result["generation_failed"] is True
    assert result["original_text"] == "A alma é imortal."
    assert result["explanation"] == ""


def test_study_excludes_same_item_from_related():
    same_item_chunk = {**_CHUNK, "distance": 0.1}
    other_chunk = {
        "content": "outro texto",
        "metadata": {"book": "O Livro dos Espíritos", "item_number": "200", "chapter_title": ""},
        "distance": 0.4,
    }
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[same_item_chunk, other_chunk]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert all(r["item_number"] != "150" for r in result["related_items"])


def test_study_sources_include_chunk_metadata():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["sources"][0]["item_number"] == "150"
    assert result["sources"][0]["book"] == "O Livro dos Espíritos"
    assert result["sources"][0]["chapter_title"] == "Da Alma"


def test_study_forwards_chapter_to_retrieve_by_item():
    with patch("src.rag.study.retrieve_by_item") as mock_retrieve:
        mock_retrieve.return_value = []
        study("O Evangelho Segundo o Espiritismo", "1", chapter="CAPÍTULO IV")
    mock_retrieve.assert_called_once_with(
        "O Evangelho Segundo o Espiritismo", "1", "CAPÍTULO IV"
    )
