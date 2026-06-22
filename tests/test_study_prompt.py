import pytest
from src.rag.study_prompt import build_study_messages, parse_llm_json


_RELATED = [
    {
        "content": "O espírito evolui.",
        "metadata": {"book": "O Livro dos Espíritos", "item_number": "100"},
        "distance": 0.3,
    }
]


def test_main_passage_appears_in_system():
    system, _ = build_study_messages("alma e corpo", [])
    assert "alma e corpo" in system


def test_related_passage_appears_in_system():
    system, _ = build_study_messages("texto", _RELATED)
    assert "O espírito evolui." in system


def test_json_instruction_in_system():
    system, _ = build_study_messages("texto", [])
    assert "JSON" in system


def test_messages_contains_user_prompt():
    _, messages = build_study_messages("texto", [])
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert isinstance(messages[0]["content"], str)


def test_parse_llm_json_extracts_fields():
    text = '{"explanation": "A alma existe.", "practical_example": "Como quando sonhamos."}'
    expl, ex = parse_llm_json(text)
    assert expl == "A alma existe."
    assert ex == "Como quando sonhamos."


def test_parse_llm_json_strips_markdown_fences():
    text = '```json\n{"explanation": "A.", "practical_example": "B."}\n```'
    expl, ex = parse_llm_json(text)
    assert expl == "A."
    assert ex == "B."


def test_parse_llm_json_falls_back_on_invalid_json():
    text = "não é JSON válido"
    expl, ex = parse_llm_json(text)
    assert expl == "não é JSON válido"
    assert ex == ""
