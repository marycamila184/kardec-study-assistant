from unittest.mock import MagicMock, patch

from src.rag.generate_chapter_summaries import generate_summaries, group_chapters

_CHUNKS = [
    {"chapter_title": "Capítulo A", "content": "Parte 1 do capítulo A."},
    {"chapter_title": "Capítulo A", "content": "Parte 2 do capítulo A."},
    {"chapter_title": "Capítulo B", "content": "Único parágrafo do capítulo B."},
]


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_group_chapters_joins_content_in_order():
    grouped = group_chapters(_CHUNKS)
    assert grouped["Capítulo A"] == "Parte 1 do capítulo A. Parte 2 do capítulo A."
    assert grouped["Capítulo B"] == "Único parágrafo do capítulo B."


def test_group_chapters_preserves_chapter_order():
    grouped = group_chapters(_CHUNKS)
    assert list(grouped.keys()) == ["Capítulo A", "Capítulo B"]


def test_generate_summaries_calls_llm_for_new_chapters():
    with patch("src.rag.generate_chapter_summaries._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(
            "Resumo do capítulo A."
        )
        result = generate_summaries(_CHUNKS, existing={})
    assert result["Capítulo A"] == "Resumo do capítulo A."
    assert result["Capítulo B"] == "Resumo do capítulo A."  # same mocked response for both calls


def test_generate_summaries_skips_existing_chapters_without_force():
    with patch("src.rag.generate_chapter_summaries._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(
            "Novo resumo."
        )
        result = generate_summaries(
            _CHUNKS, existing={"Capítulo A": "Resumo antigo revisado."}
        )
    assert result["Capítulo A"] == "Resumo antigo revisado."
    assert result["Capítulo B"] == "Novo resumo."
    mock_client.return_value.chat.completions.create.assert_called_once()


def test_generate_summaries_force_regenerates_existing_chapters():
    with patch("src.rag.generate_chapter_summaries._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(
            "Resumo regenerado."
        )
        result = generate_summaries(
            _CHUNKS, existing={"Capítulo A": "Resumo antigo."}, force=True
        )
    assert result["Capítulo A"] == "Resumo regenerado."
    assert mock_client.return_value.chat.completions.create.call_count == 2


def test_generate_summaries_continues_on_llm_failure_for_one_chapter(capsys):
    def side_effect_func(*args, **kwargs):
        # First call (Capítulo A) succeeds; second call (Capítulo B) fails
        if side_effect_func.call_count == 0:
            side_effect_func.call_count += 1
            return _make_llm_response("Resumo do capítulo A.")
        else:
            side_effect_func.call_count += 1
            raise RuntimeError("API error on chapter B")

    side_effect_func.call_count = 0

    with patch("src.rag.generate_chapter_summaries._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = side_effect_func
        result = generate_summaries(_CHUNKS, existing={})

    # Capítulo A should be in the result (first call succeeded)
    assert result["Capítulo A"] == "Resumo do capítulo A."
    # Capítulo B should NOT be in the result (LLM call raised)
    assert "Capítulo B" not in result

    # Verify warning was printed
    captured = capsys.readouterr()
    assert "Warning: Failed to summarize chapter 'Capítulo B'" in captured.out
