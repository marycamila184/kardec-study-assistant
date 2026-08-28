"""Envio de uma notificação, e o tratamento do aparelho que sumiu."""

import json

from pywebpush import webpush

from src.core.config import settings
from src.push.store import Subscription

REMINDER_TITLE = "Dialogando com a Doutrina 📖"
REMINDER_BODY = "É a hora do seu estudo. Que tal começar pelo trecho de hoje?"
# O mesmo destino que o card "☀️ Trecho do dia" da barra lateral já abre.
REMINDER_URL = "/?mode=trecho"


class Gone(Exception):
    """O serviço de push diz que este endpoint não existe mais."""


def send(sub: Subscription) -> None:
    """Envia o lembrete. Levanta Gone quando o registro deve ser apagado.

    410 e 404 são as duas respostas que significam "esse aparelho acabou" —
    qualquer outra falha é transitória e o Job simplesmente tenta de novo no
    dia seguinte, sem apagar nada.
    """
    resposta = webpush(
        subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
        data=json.dumps(
            {"title": REMINDER_TITLE, "body": REMINDER_BODY, "url": REMINDER_URL}
        ),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
    )
    if resposta.status_code in (404, 410):
        raise Gone(sub.endpoint)
