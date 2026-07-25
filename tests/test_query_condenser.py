from unittest.mock import MagicMock, patch

from src.rag.query_condenser import ANCHOR_CAP, blend_anchor, condense_query


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_condense_query_returns_stripped_content():
    history = [{"role": "user", "content": "O que é reencarnação?"}]
    with patch("src.rag.query_condenser.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response("  consulta reescrita  ")
        )
        result = condense_query("e o que mais?", history)
    assert result == "consulta reescrita"


def test_condense_query_sends_history_and_question_to_llm():
    history = [{"role": "user", "content": "pergunta anterior"}]
    with patch("src.rag.query_condenser.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response("x")
        )
        condense_query("nova pergunta", history)
        prompt = mock_client.return_value.chat.completions.create.call_args.kwargs[
            "messages"
        ][0]["content"]
    assert "pergunta anterior" in prompt
    assert "nova pergunta" in prompt


def test_blend_anchor_prepends_capped_anchor():
    result = blend_anchor("minha pergunta", "contexto do estudo")
    assert result == "contexto do estudo\nminha pergunta"


def test_blend_anchor_caps_long_anchor_at_500_chars():
    long_anchor = "a" * 900
    result = blend_anchor("q", long_anchor)
    assert result == ("a" * ANCHOR_CAP) + "\nq"
    assert ANCHOR_CAP == 500


def test_blend_anchor_returns_query_unchanged_when_no_anchor():
    assert blend_anchor("q", None) == "q"
    assert blend_anchor("q", "") == "q"
    assert blend_anchor("q", "   ") == "q"
