"""Deterministic abuse guards that run before any model call.

The service is public and unauthenticated, and the real cost is tokens, not
compute. These two guards exist so the Together spend cap never has to be the
thing that stops abuse — that cap protects the wallet *after* the fact and takes
the app down for everyone when it trips.

Both live here rather than inside `generator.py` for the same reason the crisis
layer lives in `crisis.py`: a guard shared by several routes belongs to none of
them.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

# A study question does not run 1000 words. A message that long is pasted book
# text, a probe, or an attempt to make the prompt swallow expensive context —
# and the token bill scales with it.
MAX_WORDS = 1000

# Per IP, on the routes that call a model. Deliberately generous: a reader
# working through a chapter asks a handful of questions in ten minutes, not
# twenty.
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_S = 600

TOO_LONG_MESSAGE = (
    "Sua mensagem ficou longa demais para eu acompanhar de uma vez — o limite "
    "é de mil palavras, contando a conversa até aqui.\n\n"
    "Se você colou um trecho de uma obra, tente me enviar só a parte que gerou "
    "a dúvida. E se a pergunta foi crescendo junto com a conversa, começar uma "
    "conversa nova costuma deixar tudo mais claro para nós dois."
)

RATE_LIMITED_MESSAGE = (
    "Você fez muitas perguntas em pouco tempo e eu preciso de uma pausa curta. "
    "Tente de novo em alguns minutos — o estudo não tem pressa."
)

# ip -> timestamps of recent requests. Per instance, deliberately: see the
# limitation note in check_rate_limit.
_hits: dict[str, deque] = defaultdict(deque)


def count_words(*texts: str) -> int:
    return sum(len(t.split()) for t in texts if t)


def exceeds_size_limit(question: str, history: list[dict] | None = None) -> bool:
    """History counts toward the same ceiling.

    `max_history_turns` caps how many turns are kept, not how big they are: ten
    turns of 900 words each would pass the turn cap and cost far more than the
    single message this guard blocks.
    """
    texts = [question]
    for message in history or []:
        content = message.get("content") if isinstance(message, dict) else None
        if content:
            texts.append(content)
    return count_words(*texts) > MAX_WORDS


def client_ip(request: Request) -> str:
    """Behind Cloud Run, `request.client.host` is the load balancer — using it
    would rate-limit the entire internet as if it were one user. The real
    address is the first entry of X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> int | None:
    """Returns seconds to wait when the caller is over the limit, else None.

    The counter is per instance and resets on redeploy, so with max-instances 3
    the effective ceiling can be up to 3x the nominal one. This is a guard
    against abuse, not a contractual quota — the exact version (Redis, Cloud
    Armor) costs money and operations this stage does not justify. The
    imprecision is written down so nobody trusts it as exact.
    """
    now = time.monotonic()
    window = _hits[ip]
    while window and now - window[0] > RATE_LIMIT_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        return int(RATE_LIMIT_WINDOW_S - (now - window[0])) + 1
    window.append(now)
    return None


def reset() -> None:
    """Test seam: the module-level counter would otherwise leak across tests."""
    _hits.clear()
