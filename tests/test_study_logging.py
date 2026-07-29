"""/study não deixava rastro nenhum — e o caso que motivou a spec veio de lá.

Emite `event: "chat_turn"` com `mode: "study"` de propósito: a consulta que lê
qualidade não deve ter de unir dois eventos diferentes.

Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# O corpo que study_item_fn devolve, com os campos obrigatórios de
# StudyResponse — se faltar um, o erro é 500 e não a asserção do teste.
_STUDY_RESULT = {
    "original_text": "1. Que é Deus? “Deus é a inteligência suprema…”",
    "contexto": "O item abre O Livro dos Espíritos…",
    "inline_refs": [],
    "conceitos_chave": [],
    "perguntas": [],
    "related_items": [],
    "sources": [{"book": "O Livro dos Espíritos", "item_number": "1"}],
    "chapter_context": [],
    "generation_failed": False,
    "retrieved": [
        {
            "book": "O Livro dos Espíritos",
            "chapter": "DE DEUS",
            "item": "1",
            "distance": 0.0,
        }
    ],
}


def _post(stream, **kwargs):
    with patch("src.api.routes.study_item_fn", return_value=dict(_STUDY_RESULT)):
        res = client.post(
            "/study",
            json={"book": "O Livro dos Espíritos", "item_number": "1"},
            **kwargs,
        )
    return res, json.loads(stream.getvalue().strip())


def test_study_logs_one_line_with_mode_study(stream):
    res, line = _post(stream)
    assert res.status_code == 200
    assert line["event"] == "chat_turn"
    assert line["mode"] == "study"
    assert line["turn_id"] == res.json()["turn_id"]


def test_study_question_field_names_the_item_not_a_question(stream):
    _, line = _post(stream)
    # Não há pergunta digitada num estudo. O campo carrega a referência, para
    # que uma consulta única sobre chat_turn continue legível.
    assert line["question"] == "O Livro dos Espíritos — item 1"


def test_study_without_header_has_no_session(stream):
    _, line = _post(stream)
    assert "session_id" not in line


def test_study_with_header_carries_the_session(stream):
    _, line = _post(stream, headers={"X-Session-Id": "sess-study"})
    assert line["session_id"] == "sess-study"


def test_study_carries_the_retrieved_set(stream):
    _, line = _post(stream)
    assert line["retrieved"] == _STUDY_RESULT["retrieved"]


def test_retrieved_never_reaches_the_client(stream):
    """Campo de log, não de resposta. Se vazasse, viraria contrato público."""
    res, _ = _post(stream)
    assert "retrieved" not in res.json()


def test_stream_lane_logs_the_same_line(stream):
    """Um estudo streamado e um não-streamado produzem a mesma linha."""
    ctx = {
        "original_text": _STUDY_RESULT["original_text"],
        "chunks": [],
        "related": [],
        "commentary": [],
    }

    def fake_stream(_ctx):
        yield "token", "O item"
        yield "done", dict(_STUDY_RESULT)

    with (
        patch("src.api.routes.prepare_study", return_value=ctx),
        patch("src.api.routes.build_sources", return_value=[]),
        patch("src.api.routes.explicar_stream", fake_stream),
    ):
        res = client.post(
            "/study/stream",
            json={"book": "O Livro dos Espíritos", "item_number": "1"},
            headers={"X-Session-Id": "sess-study"},
        )

    line = json.loads(stream.getvalue().strip())
    assert line["mode"] == "study"
    assert line["session_id"] == "sess-study"
    done = json.loads(res.text.rsplit("event: done\ndata: ", 1)[1].strip())
    assert done["turn_id"] == line["turn_id"]
