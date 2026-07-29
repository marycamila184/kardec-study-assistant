"""O consentimento viaja como a presença do header. A ausência é a recusa.

O backend nunca gera um session_id e nunca cai para IP: se o header não veio,
não existe sessão. Um bug de frontend erra para o lado seguro — o pior caso é
perder log, não gravar sem consentimento.

Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_RESULT = {
    "answer": "Kardec escreve que o perispírito é o envoltório fluídico.",
    "sources": [],
    "not_found": False,
    "retrieved": [
        {"book": "A Gênese", "chapter": "OS FLUIDOS", "item": "22", "distance": 0.31}
    ],
}


def _offline():
    """Todo caminho de rede de /chat, mockado.

    São três, e o terceiro é fácil de esquecer: `detect_profile_changes` é uma
    chamada de LLM que roda antes da geração. Sem ele mockado o teste sai na
    rede de verdade, falha com 401 e só passa porque a rota degrada com
    elegância — passando por acidente, e devagar.
    """
    return [
        patch("src.api.routes.generate", return_value=_RESULT),
        patch("src.api.routes.classify_intent", return_value={"mode": None}),
        patch("src.api.routes.detect_profile_changes", side_effect=lambda _q, p: p),
    ]


def _post(stream, path="/chat", body=None, **kwargs):
    """Uma requisição com o pipeline mockado, devolvendo (resposta, linha).

    O mock é obrigatório: sem ele o teste chamaria o provedor de verdade. E a
    linha vem da fixture `stream` do conftest, não de caplog — o logger
    `conversation` tem propagate=False de propósito, então caplog não vê nada.
    """
    with ExitStack() as stack:
        for ctx in _offline():
            stack.enter_context(ctx)
        res = client.post(
            path, json=body or {"question": "o que é o perispírito?"}, **kwargs
        )
    return res, json.loads(stream.getvalue().strip())


def test_no_header_means_no_session(stream):
    res, line = _post(stream)
    assert res.status_code == 200
    assert "session_id" not in line


def test_header_is_echoed_into_the_log(stream):
    res, line = _post(stream, headers={"X-Session-Id": "sess-abc"})
    assert res.status_code == 200
    assert line["session_id"] == "sess-abc"


def test_turn_id_in_body_matches_the_log(stream):
    res, line = _post(stream)
    assert res.json()["turn_id"] == line["turn_id"]


def test_backend_never_invents_a_session_from_the_ip(stream):
    _, line = _post(stream, headers={"X-Forwarded-For": "203.0.113.9"})
    assert "session_id" not in line
    assert "203.0.113.9" not in json.dumps(line)


def test_empty_header_is_refusal_not_a_session(stream):
    _, line = _post(stream, headers={"X-Session-Id": ""})
    assert "session_id" not in line


def test_debug_fields_are_present(stream):
    _, line = _post(stream)
    assert line["mode"] == "chat"
    assert line["provider"]
    assert line["model"]
    assert line["n_history"] == 0
    assert line["retrieved"] == _RESULT["retrieved"]


def test_history_is_counted_never_recorded(stream):
    """Regra nº2 de 27/07: o histórico não é registrado. Só quantos turnos."""
    body = {
        "question": "e sobre isso?",
        "history": [
            {"role": "user", "content": "o que é a prece?"},
            {"role": "assistant", "content": "Kardec escreve que a prece…"},
        ],
    }
    _, line = _post(stream, body=body)
    assert line["n_history"] == 2
    assert "o que é a prece?" not in json.dumps(line, ensure_ascii=False)


def test_stream_lane_logs_the_same_session(stream):
    """As duas vias registram o mesmo, ou o log mente sobre metade do tráfego."""

    def fake_stream(*args, **kwargs):
        yield "token", "Kardec"
        yield "done", _RESULT

    with ExitStack() as stack:
        stack.enter_context(patch("src.api.routes.generate_stream", fake_stream))
        stack.enter_context(
            patch("src.api.routes.classify_intent", return_value={"mode": None})
        )
        stack.enter_context(
            patch("src.api.routes.detect_profile_changes", side_effect=lambda _q, p: p)
        )
        res = client.post(
            "/chat/stream",
            json={"question": "o que é o perispírito?"},
            headers={"X-Session-Id": "sess-stream"},
        )
        body = res.text

    line = json.loads(stream.getvalue().strip())
    assert line["session_id"] == "sess-stream"
    assert line["mode"] == "chat"
    # O turn_id do evento `done` é o mesmo que foi para o log.
    done = json.loads(body.rsplit("event: done\ndata: ", 1)[1].strip())
    assert done["turn_id"] == line["turn_id"]
