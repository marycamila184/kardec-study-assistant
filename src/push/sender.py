"""Envio de uma notificação, e o tratamento do aparelho que sumiu."""

import json

from pywebpush import WebPushException, webpush

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

    O pywebpush não devolve a resposta para quem chama conferir: ele levanta
    WebPushException em qualquer status acima de 202, com a resposta pendurada
    em `.response`. Uma versão anterior deste arquivo lia `status_code` do
    retorno, o que nunca acontecia — o caminho do Gone era código morto e
    aparelho apagado nunca teria sido apagado do store.

    410 e 404 são as duas respostas que significam "esse aparelho acabou".
    Qualquer outra falha é transitória e sobe como está: quem chama trata como
    falha do dia e NÃO apaga nada.
    """
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
            data=json.dumps(
                {"title": REMINDER_TITLE, "body": REMINDER_BODY, "url": REMINDER_URL}
            ),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
    except WebPushException as erro:
        status = getattr(erro.response, "status_code", None)
        if status in (404, 410):
            raise Gone(sub.endpoint) from erro
        raise
