from unittest.mock import MagicMock, patch

from src.rag.explicador import explicar

_CHUNK_WITH_FOOTNOTE = {
    "content": "1. Que é Deus?",
    "footnote_context": "[Nota 1] Explicação editorial de exemplo.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Noções Preliminares",
        "item_number": "1",
    },
    "distance": 0.0,
}


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_explicar_returns_none_when_no_chunks():
    with patch("src.rag.explicador.retrieve_by_item", return_value=[]):
        result = explicar("O Livro dos Espíritos", "1")
    assert result is None


def test_explicar_passes_footnote_context_to_prompt():
    llm_json = '{"contexto": "Contexto de teste.", "conceitos_chave": [], "perguntas": []}'
    with (
        patch("src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador.build_explicador_messages") as mock_build,
        patch("src.rag.explicador._get_client") as mock_client,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(llm_json)
        explicar("O Livro dos Espíritos", "1")
    assert mock_build.call_args.kwargs["footnote_context"] == "[Nota 1] Explicação editorial de exemplo."


def test_explicar_returns_contexto_from_llm():
    llm_json = '{"contexto": "Contexto de teste.", "conceitos_chave": [], "perguntas": []}'
    with (
        patch("src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(llm_json)
        result = explicar("O Livro dos Espíritos", "1")
    assert result["contexto"] == "Contexto de teste."
    assert result["original_text"] == "1. Que é Deus?"
