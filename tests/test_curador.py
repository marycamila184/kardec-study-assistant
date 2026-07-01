from unittest.mock import MagicMock, patch

from src.rag.curador import curar

_CANDIDATE_1 = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO I",
        "chapter_title": "Da Alma",
        "item_number": "1",
    },
    "distance": 0.3,
}

_CANDIDATE_2 = {
    "content": "A angústia é uma prova da alma.",
    "metadata": {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO II",
        "chapter_title": "Da Encarnação",
        "item_number": "1",
    },
    "distance": 0.5,
}


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_curar_returns_empty_for_no_candidates():
    assert curar("trecho principal", []) == []


def test_curar_includes_chapter_when_llm_selects_candidate():
    llm_json = '[{"index": 0, "conexao": "Conecta pela imortalidade da alma."}]'
    with patch("src.rag.curador._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(llm_json)
        result = curar("trecho principal", [_CANDIDATE_1])
    assert result[0]["chapter"] == "CAPÍTULO I"


def test_curar_includes_chapter_in_fallback_when_llm_fails():
    with patch("src.rag.curador._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API error")
        result = curar("trecho principal", [_CANDIDATE_1, _CANDIDATE_2])
    assert result[0]["chapter"] == "CAPÍTULO I"
    assert result[1]["chapter"] == "CAPÍTULO II"


def test_curar_includes_chapter_in_fallback_when_llm_returns_no_selections():
    with patch("src.rag.curador._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response("[]")
        result = curar("trecho principal", [_CANDIDATE_1])
    assert result[0]["chapter"] == "CAPÍTULO I"
