"""What the Cloud Run Job runs, hourly.

Runs the same image as the API with a different command, on purpose: an
endpoint on the API would require validating OIDC on a public surface, and
this Job has no surface at all.

Run with: python -m src.push.dispatch
"""

import logging
from datetime import datetime, timezone

from src.core.config import settings
from src.push import sender, store
from src.push.schedule import is_due
from src.rag import reflection_cache
from src.rag.evangelho import get_daily_passage
from src.rag.explicador import explicar as study_item_fn

logger = logging.getLogger(__name__)


def _warm_cache(passage: dict | None) -> None:
    """Ensures the day's explanation is in the cache, before any sending.

    A lazy cache defeats itself precisely because the reminder works: at
    08:00 the notification reaches everyone at once, everyone opens within
    seconds, everyone finds the cache empty, and one call a day becomes
    dozens inside a minute — each of those readers waiting for the stream
    the cache existed to remove.

    A failure here must never hold up the reminder: whoever opens it falls
    through to the normal path, with the stream, exactly as it does today.
    """
    if passage is None:
        return
    if reflection_cache.get(passage) is not None:
        return
    s = passage.get("source", {})
    try:
        result = study_item_fn(
            s.get("book"), s.get("item_number"), s.get("chapter"), s.get("part")
        )
    except Exception:
        logger.exception("failed to warm the reflection cache")
        return
    if result and not result.get("generation_failed"):
        reflection_cache.put(passage, result)


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

    # Uma leitura só da coleção inteira por execução. A varredura dos 90 dias
    # logo abaixo reaproveita esta mesma lista em vez de ler de novo — ler
    # duas vezes por tique dobraria as leituras do Firestore (192 varreduras
    # completas por dia), o que cruza o nível grátis com poucas centenas de
    # aparelhos e só aparece na fatura.
    inscricoes = store.all_subscriptions()

    # The day's chapter, for the notification body. get_daily_passage is
    # deterministic and calls no model. If it fails, the reminder still goes
    # out with the generic text: an invitation with no theme beats no
    # reminder at all.
    try:
        passagem = get_daily_passage()
        capitulo = (passagem or {}).get("source", {}).get("chapter_title")
    except Exception:
        logger.exception("falha ao ler o trecho do dia")
        passagem, capitulo = None, None

    _warm_cache(passagem)

    for sub in inscricoes:
        if not is_due(sub.hour, sub.timezone, agora, settings.push_window_minutes):
            continue
        try:
            sender.send(sub, chapter_title=capitulo)
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
        today=agora.date(),
        max_age_days=settings.push_expiry_days,
        subscriptions=inscricoes,
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
