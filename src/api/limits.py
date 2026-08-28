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

# The ceiling counts only what the READER wrote — the new question plus the
# user turns in the history. The assistant's turns are excluded on purpose:
# they are generated here and already bounded by max_tokens, so the part that
# can grow without limit is the input. Counting our own output against the
# reader's budget is what made a long conversation refuse an eight-word
# question in production (2026-07-28).
MAX_WORDS = 2000

# Per IP, on the routes that call a model. Deliberately generous: a reader
# working through a chapter asks a handful of questions in ten minutes, not
# twenty.
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_S = 600

# Only ever shown for a single over-long message now. A long CONVERSATION is
# handled by dropping its oldest turns (see trim_history), so nobody is stopped
# for having got far. The old wording blamed "sua mensagem" while counting the
# history, which in production told someone their eight-word question was too
# long.
TOO_LONG_MESSAGE = (
    "Sua mensagem ficou longa demais para eu acompanhar de uma vez — o limite "
    "é de duas mil palavras.\n\n"
    "Se você colou um trecho de uma obra, tente me enviar só a parte que gerou "
    "a dúvida."
)

RATE_LIMITED_MESSAGE = (
    "Você fez muitas perguntas em pouco tempo e eu preciso de uma pausa curta. "
    "Tente de novo em alguns minutos — o estudo não tem pressa."
)

# "bucket:ip" -> timestamps of recent requests. Per instance, deliberately:
# see the limitation note in check_rate_limit. Keyed by bucket as well as IP
# so unrelated routes don't share one counter — see check_rate_limit.
_hits: dict[str, deque] = defaultdict(deque)

# Default bucket name, unchanged from before buckets existed: every call site
# that does not pass one keeps counting against the same shared counter as
# always.
_DEFAULT_BUCKET = "default"


def count_words(*texts: str) -> int:
    return sum(len(t.split()) for t in texts if t)


def exceeds_size_limit(question: str, history: list[dict] | None = None) -> bool:
    """Whether the NEW message alone is over the ceiling.

    History is no longer counted here. It used to be, and the effect in
    production (2026-07-28) was that a long conversation refused an eight-word
    question and could never accept another one — history only grows, so the
    refusal was permanent and the only way out was starting over. The cost
    concern that motivated counting it is real; it is answered by trimming the
    history instead (see trim_history), which keeps the budget and the
    conversation.

    `history` is accepted and ignored so existing call sites keep working.
    """
    return count_words(question) > MAX_WORDS


def _is_user(message: dict) -> bool:
    return message.get("role") == "user"


def trim_history(question: str, history: list[dict] | None) -> list[dict]:
    """Drops the OLDEST turns until the reader's own words fit the ceiling.

    Oldest first because the recent turns are what a follow-up fragment ("e
    sobre isso?") needs to be understood; the opening of a long conversation is
    the part nobody is still referring to.

    `max_history_turns` caps how MANY turns are kept, not how big they are — ten
    turns of 900 words would pass that cap and cost far more than the single
    message this guard blocks. This is the size half of the same budget.
    """
    kept = [
        m
        for m in (history or [])
        if (m.get("content") if isinstance(m, dict) else None)
    ]
    budget = MAX_WORDS - count_words(question)
    if budget <= 0:
        return []

    total = 0
    out: list[dict] = []
    # Walk backwards from the most recent turn, keeping while the reader's words
    # fit. An assistant turn costs nothing against the budget but is still
    # dropped once the user turn it answers is gone — a reply with no question
    # in front of it reads as the assistant talking to itself.
    for message in reversed(kept):
        if _is_user(message):
            words = count_words(message["content"])
            if total + words > budget:
                break
            total += words
        out.append(message)
    out.reverse()

    # The walk stops ON a user turn, so the assistant turn just after it may
    # already be in `out` with its question gone. Drop any reply that no longer
    # has the question it answers in front of it.
    while out and not _is_user(out[0]):
        out.pop(0)
    return out


def client_ip(request: Request) -> str:
    """Behind Cloud Run, `request.client.host` is the load balancer — using it
    would rate-limit the entire internet as if it were one user. The real
    address is the first entry of X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str, bucket: str = _DEFAULT_BUCKET) -> int | None:
    """Returns seconds to wait when the caller is over the limit, else None.

    The counter is per instance and resets on redeploy, so with max-instances 3
    the effective ceiling can be up to 3x the nominal one. This is a guard
    against abuse, not a contractual quota — the exact version (Redis, Cloud
    Armor) costs money and operations this stage does not justify. The
    imprecision is written down so nobody trusts it as exact.

    `bucket` separates independent counters that share this same function —
    /chat and /study default to one shared bucket, and /push/subscribe passes
    its own. Without this, someone who had been asking questions would see
    the reminder toggle refuse them, and fiddling with the reminder hour could
    burn the budget for their next real question. The reminder is not a
    conversation and must not spend the conversation's budget, or vice versa.
    """
    now = time.monotonic()
    window = _hits[f"{bucket}:{ip}"]
    while window and now - window[0] > RATE_LIMIT_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        return int(RATE_LIMIT_WINDOW_S - (now - window[0])) + 1
    window.append(now)
    return None


def reset() -> None:
    """Test seam: the module-level counter would otherwise leak across tests."""
    _hits.clear()
