"""O voto vale mesmo sem consentimento: {turn_id, vote} não descreve pessoa.

Recusar o banner não tira de ninguém a capacidade de dizer que a resposta foi
ruim.

Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.rag import conversation_log

client = TestClient(app)

# Sem patch de pipeline aqui, e de propósito: /feedback não chama pipeline
# nenhum. Se um dia precisar de mock, é sinal de que a rota passou a fazer mais
# do que registrar um voto.


def test_vote_is_logged(stream):
    res = client.post("/feedback", json={"turn_id": "t-1", "vote": "down"})
    assert res.status_code == 204
    assert json.loads(stream.getvalue().strip()) == {
        "event": "feedback",
        "severity": "INFO",
        "turn_id": "t-1",
        "vote": "down",
    }


def test_vote_carries_session_when_consented(stream):
    client.post(
        "/feedback",
        json={"turn_id": "t-1", "vote": "up"},
        headers={"X-Session-Id": "sess-abc"},
    )
    assert json.loads(stream.getvalue().strip())["session_id"] == "sess-abc"


def test_invalid_vote_is_rejected():
    res = client.post("/feedback", json={"turn_id": "t-1", "vote": "talvez"})
    assert res.status_code == 422


def test_feedback_never_carries_text(stream):
    """Escopo fechado: só polegar.

    Uma caixa de texto livre reabriria toda a discussão de dado sensível que a
    spec resolveu — então um campo extra enviado pelo cliente é ignorado pelo
    schema e nunca chega ao log.
    """
    res = client.post(
        "/feedback", json={"turn_id": "t-1", "vote": "down", "comment": "odiei"}
    )
    assert res.status_code == 204
    assert "odiei" not in stream.getvalue()


def test_logging_failure_does_not_fail_the_vote(stream):
    """Observabilidade não pode derrubar o que já funcionou — nem aqui.

    Quebra o logger de verdade, não a função que o envolve: `log_feedback` já
    engole exceções, então mocká-la para levantar testaria o mock. O que
    interessa é que uma falha real de escrita não vire erro para quem votou.
    """
    with patch.object(
        conversation_log._logger, "info", side_effect=RuntimeError("disco cheio")
    ):
        res = client.post("/feedback", json={"turn_id": "t-1", "vote": "up"})
    assert res.status_code == 204
