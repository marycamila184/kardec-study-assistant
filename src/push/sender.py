"""Envio de uma notificação, e o tratamento do aparelho que sumiu."""

import json

from pywebpush import WebPushException, webpush

from src.core.config import settings
from src.push.store import Subscription

REMINDER_TITLE = "Dialogando com a Doutrina"
# No chapter of the day — only when get_daily_passage fails.
REMINDER_FALLBACK = "A reflexão de hoje está esperando por você."
# Same destination the "☀️ Trecho do dia" card in the sidebar already opens.
REMINDER_URL = "/?mode=trecho"


class Gone(Exception):
    """O serviço de push diz que este endpoint não existe mais."""


def _corpo(chapter_title: str | None) -> str:
    """The notification body: the day's chapter, unchanged.

    The all-caps form comes from the corpus and is how the app already
    displays these titles. Lowercasing it would need an exception list for
    DEUS, JESUS and CRISTO, and getting that wrong once in an app about this
    doctrine costs more than the capitals do.

    The passage text does not go here: it's ~517 characters, would be
    truncated, and truncating a passage is the error the 2026-08-05 curation
    fixed — 23 passages were cut before their ending, which in the Evangelho
    is usually the merciful part.
    """
    if not chapter_title:
        return REMINDER_FALLBACK
    return f"Reflexão de hoje — {chapter_title}"


def send(sub: Subscription, chapter_title: str | None = None) -> None:
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
                {
                    "title": REMINDER_TITLE,
                    "body": _corpo(chapter_title),
                    "url": REMINDER_URL,
                }
            ),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
    except WebPushException as erro:
        status = getattr(erro.response, "status_code", None)
        if status in (404, 410):
            raise Gone(sub.endpoint) from erro
        raise
