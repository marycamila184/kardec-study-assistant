from datetime import date
from unittest.mock import patch

import pytest
from pywebpush import WebPushException

from src.push.sender import Gone, send
from src.push.store import Subscription

_SUB = Subscription(
    endpoint="https://push.example/abc",
    keys={"p256dh": "chave", "auth": "segredo"},
    hour="08:00",
    timezone="America/Sao_Paulo",
    last_seen=date(2026, 8, 27),
)


def _falha(status):
    """Uma WebPushException como o pywebpush a levanta de verdade."""

    class _R:
        status_code = status
        reason = "erro"
        text = ""

    return WebPushException("falhou", response=_R())


def test_410_vira_Gone():
    # O serviço de push dizendo 410 significa "este aparelho não existe
    # mais". Reenviar é inútil; o registro sai na hora.
    with patch("src.push.sender.webpush", side_effect=_falha(410)):
        with pytest.raises(Gone):
            send(_SUB)


def test_404_tambem_vira_Gone():
    with patch("src.push.sender.webpush", side_effect=_falha(404)):
        with pytest.raises(Gone):
            send(_SUB)


def test_erro_transitorio_nao_vira_Gone():
    # 503 é o serviço de push com problema, não o aparelho. Tem de subir como
    # veio, para que quem chama NÃO apague a inscrição de ninguém por causa
    # de um minuto ruim.
    with patch("src.push.sender.webpush", side_effect=_falha(503)):
        with pytest.raises(WebPushException):
            send(_SUB)


def test_sucesso_nao_levanta():
    with patch("src.push.sender.webpush", return_value=None):
        send(_SUB)


def test_a_notificacao_leva_titulo_corpo_e_destino():
    with patch("src.push.sender.webpush") as enviar:
        send(_SUB)
    payload = enviar.call_args.kwargs["data"]
    assert "Dialogando" in payload
    assert "trecho" in payload
