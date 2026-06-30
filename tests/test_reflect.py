from unittest.mock import MagicMock, patch

from src.rag.reflect import reflect

_CHUNK_1 = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "150",
        "chapter_title": "Da Alma",
    },
    "distance": 0.3,
}
_CHUNK_2 = {
    "content": "A angústia é uma prova da alma.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "132",
        "chapter_title": "Da Encarnação",
    },
    "distance": 0.5,
}
_CHUNK_3 = {
    "content": "O amor é a lei suprema.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "item_number": "section-1",
        "chapter_title": "",
    },
    "distance": 0.7,
}

_LLM_JSON = '{"opening": "Compreendemos sua dor.", "doctrine_connection": "A doutrina ensina...", "reflection_questions": ["Q1?", "Q2?", "Q3?"]}'


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_reflect_returns_not_found_when_no_chunks():
    with patch("src.rag.reflect.retrieve", return_value=[]):
        result = reflect("meu pai faleceu")
    assert result["not_found"] is True
    assert result["generation_failed"] is False
    assert result["opening"] == ""
    assert result["complementary_items"] == []
    assert result["sources"] == []


def test_reflect_returns_opening_from_llm():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("meu pai faleceu")
    assert result["opening"] == "Compreendemos sua dor."
    assert result["not_found"] is False


def test_reflect_returns_reflection_questions():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("meu pai faleceu")
    assert result["reflection_questions"] == ["Q1?", "Q2?", "Q3?"]


def test_reflect_sets_generation_failed_on_llm_error():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API error")
        result = reflect("situação")
    assert result["generation_failed"] is True
    assert result["opening"] == ""
    assert result["not_found"] is False


def test_reflect_sources_come_from_first_two_chunks():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2, _CHUNK_3]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("situação")
    assert len(result["sources"]) == 2
    item_numbers = [s["item_number"] for s in result["sources"]]
    assert "150" in item_numbers
    assert "132" in item_numbers


def test_reflect_complementary_items_come_from_chunks_3_to_5():
    extra = [
        {
            "content": f"texto {i}",
            "metadata": {"book": "Livro X", "item_number": str(i), "chapter_title": ""},
            "distance": 0.9,
        }
        for i in range(3, 6)
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2] + extra),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("situação")
    assert len(result["complementary_items"]) == 3
    assert result["complementary_items"][0]["item_number"] == "3"


def test_reflect_passes_add_caveat_true_for_clinical_keywords():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        reflect("escuto vozes à noite")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is True


def test_reflect_passes_add_caveat_false_for_normal_situation():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        reflect("meu pai faleceu")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is False


def test_reflect_sources_include_excerpt():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("situação")
    excerpts = [s["excerpt"] for s in result["sources"]]
    assert "Os espíritos sobrevivem à morte do corpo." in excerpts
