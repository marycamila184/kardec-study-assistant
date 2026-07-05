import json

from src.rag.curador_prompt import parse_curador_json


def test_parse_curador_json_extracts_selections():
    text = json.dumps([{"index": 0, "conexao": "Conecta com o tema principal."}])
    result = parse_curador_json(text)
    assert result == [{"index": 0, "conexao": "Conecta com o tema principal."}]


def test_parse_curador_json_strips_markdown_fences():
    text = "```json\n" + json.dumps([{"index": 1, "conexao": "C"}]) + "\n```"
    result = parse_curador_json(text)
    assert result == [{"index": 1, "conexao": "C"}]


def test_parse_curador_json_extracts_array_wrapped_in_prose():
    text = (
        "Aqui estão as seleções: "
        + json.dumps([{"index": 2, "conexao": "C"}])
        + " Fim."
    )
    result = parse_curador_json(text)
    assert result == [{"index": 2, "conexao": "C"}]


def test_parse_curador_json_returns_empty_list_when_model_finds_nothing():
    text = "[]"
    assert parse_curador_json(text) == []


def test_parse_curador_json_returns_empty_list_on_unparseable_text():
    assert parse_curador_json("isto não é JSON") == []


def test_parse_curador_json_skips_items_missing_index():
    text = json.dumps([{"conexao": "sem index"}, {"index": 0, "conexao": "válido"}])
    result = parse_curador_json(text)
    assert result == [{"index": 0, "conexao": "válido"}]


def test_parse_curador_json_dedups_repeated_index():
    text = json.dumps(
        [
            {"index": 0, "conexao": "primeira menção"},
            {"index": 0, "conexao": "segunda menção duplicada"},
        ]
    )
    result = parse_curador_json(text)
    assert result == [{"index": 0, "conexao": "primeira menção"}]
