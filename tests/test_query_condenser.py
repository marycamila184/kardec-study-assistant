from unittest.mock import MagicMock, patch

from src.rag.query_condenser import condense_query


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
