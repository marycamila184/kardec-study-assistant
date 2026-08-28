from datetime import date
from unittest.mock import patch

import pytest

from src.push.sender import Gone, send
from src.push.store import Subscription

_SUB = Subscription(
    endpoint="https://push.example/abc",
    keys={"p256dh": "chave", "auth": "segredo"},
    hour="08:00",
    timezone="America/Sao_Paulo",
    last_seen=date(2026, 8, 27),
)


class _Resposta:
    def __init__(self, status_code):
        self.status_code = status_code


def test_410_vira_Gone():
    # O serviço de push dizendo 410 significa "este aparelho não existe
    # mais". Reenviar é inútil; o registro sai na hora.
    with patch("src.push.sender.webpush", return_value=_Resposta(410)):
        with pytest.raises(Gone):
            send(_SUB)


def test_404_tambem_vira_Gone():
    with patch("src.push.sender.webpush", return_value=_Resposta(404)):
        with pytest.raises(Gone):
            send(_SUB)


def test_201_passa_sem_erro():
    with patch("src.push.sender.webpush", return_value=_Resposta(201)):
        send(_SUB)


def test_a_notificacao_leva_titulo_corpo_e_destino():
    with patch("src.push.sender.webpush", return_value=_Resposta(201)) as enviar:
        send(_SUB)
    payload = enviar.call_args.kwargs["data"]
    assert "Dialogando" in payload
    assert "trecho" in payload
