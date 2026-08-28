"""Quem está na janela de envio agora.

Função pura, sem rede e sem Firestore, porque é a única lógica de verdade
desta funcionalidade: todo o resto é encanamento. Testar isto exige só um
relógio fixo.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_due(
    hour: str, timezone_name: str, now_utc: datetime, window_minutes: int
) -> bool:
    """True quando a hora local de `timezone_name` acabou de passar por `hour`.

    A janela é [início, início + window_minutes), fechada embaixo e aberta em
    cima — é isso que impede o mesmo registro de disparar em duas execuções
    consecutivas do Job.

    Entrada malformada (fuso inexistente, hora fora de HH:MM) devolve False em
    vez de levantar: os dados vêm do cliente, e um registro estragado não pode
    derrubar o envio de todos os outros.
    """
    try:
        alvo_h, alvo_m = (int(parte) for parte in hour.split(":"))
    except (ValueError, AttributeError):
        return False
    if not (0 <= alvo_h <= 23 and 0 <= alvo_m <= 59):
        return False

    try:
        local = now_utc.astimezone(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return False

    agora_min = local.hour * 60 + local.minute
    alvo_min = alvo_h * 60 + alvo_m
    # A distância à frente do alvo, dando a volta na meia-noite.
    desde_alvo = (agora_min - alvo_min) % (24 * 60)
    return desde_alvo < window_minutes
