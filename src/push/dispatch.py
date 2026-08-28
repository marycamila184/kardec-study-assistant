"""O que o Cloud Run Job executa a cada 15 minutos.

Roda a mesma imagem da API com outro comando, de propósito: um endpoint na
API exigiria validar OIDC numa superfície pública, e este Job não tem
superfície nenhuma.

Rode com: python -m src.push.dispatch
"""

import logging
from datetime import datetime, timezone

from src.core.config import settings
from src.push import sender, store
from src.push.schedule import is_due

logger = logging.getLogger(__name__)


def run(now_utc: datetime | None = None) -> dict[str, int]:
    """Envia a quem está na janela e varre os expirados. Devolve a contagem.

    Nada aqui garante idempotência: se o agendador disparar duas vezes para o
    mesmo tique, ou repetir uma execução lenta, `is_due` volta a dizer que sim
    e a pessoa recebe duas vezes. Consertar exigiria guardar a última data de
    envio por aparelho — o sexto campo, recusado. A mitigação é operacional: o
    Job é criado com --max-retries 0. Ver docs/deploy.md.
    """
    agora = now_utc or datetime.now(timezone.utc)
    contagem = {"sent": 0, "gone": 0, "failed": 0, "expired": 0}

    for sub in store.all_subscriptions():
        if not is_due(sub.hour, sub.timezone, agora, settings.push_window_minutes):
            continue
        try:
            sender.send(sub)
            contagem["sent"] += 1
        except sender.Gone:
            # Apagar pode falhar sozinho — rede, permissão. Se falhar, o
            # registro fica para a varredura dos 90 dias ou para amanhã. O que
            # não pode acontecer é a exceção subir e levar junto o lembrete de
            # todo mundo que ainda não foi processado neste ciclo.
            try:
                store.delete(sub.endpoint)
                contagem["gone"] += 1
            except Exception:
                logger.exception("falha ao apagar inscrição morta")
                contagem["failed"] += 1
        except Exception:
            # Um endpoint com problema não pode custar o lembrete de todos os
            # outros. Falha transitória: nada é apagado, tenta amanhã.
            logger.exception("falha ao enviar lembrete")
            contagem["failed"] += 1

    contagem["expired"] = store.delete_stale(
        today=agora.date(), max_age_days=settings.push_expiry_days
    )
    return contagem


def main() -> None:
    if not settings.vapid_private_key:
        logger.warning("VAPID não configurado — nada a enviar")
        return
    logger.info("dispatch: %s", run())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
