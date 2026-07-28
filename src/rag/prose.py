"""The prose lane call, with a fallback to the JSON lane.

This is a *provider* fallback only: any failure of the prose provider itself
(Ollama not running, a connection error, a non-2xx response) degrades to the
JSON lane's provider rather than to a 500. It cannot see, and does not handle,
a response that came back successfully but in the wrong *format* — the
marker-protocol parse in `explicador._call_explicador` runs after this
function returns, so a parse failure never reaches the `except` below. That
format fallback (retry once on the JSON lane with the JSON template/parser)
lives in `explicador.py` instead. When both lanes are the same provider
(PROSE_PROVIDER unset) there is nothing to fall back to here, so the error
propagates and the caller's existing generation_failed handling takes over.
"""

import logging
from typing import Iterator

from src.core.config import settings
from src.rag.llm_client import get_client

logger = logging.getLogger(__name__)


def prose_completion(
    system: str, messages: list[dict], max_tokens: int = 1024
) -> str | None:
    """Runs a prose generation on the prose lane, falling back to the JSON lane."""
    payload = [{"role": "system", "content": system}] + messages
    # temperature=0 ONLY on the real prose lane. The smoke test showed sampling
    # was the dominant grounding factor for riv-ai-v2, but pinning it while the
    # lane is off would change the current provider's output — breaking the
    # zero-behavior-change guarantee and the A/B baseline.
    extra = {"temperature": 0} if settings.prose_provider is not None else {}
    try:
        response = get_client("prose").chat.completions.create(
            model=settings.resolved_prose_model,
            max_tokens=max_tokens,
            messages=payload,
            **extra,
        )
        return response.choices[0].message.content
    except Exception:
        if settings.prose_provider is None:
            raise  # same provider on both lanes — nothing to retry
        logger.exception("prose lane failed; falling back to the json lane")

    # The fallback runs on the json lane, so it keeps that lane's defaults.
    response = get_client("json").chat.completions.create(
        model=settings.resolved_chat_model,
        max_tokens=max_tokens,
        messages=payload,
    )
    return response.choices[0].message.content


def prose_completion_stream(
    system: str, messages: list[dict], max_tokens: int = 1024
) -> Iterator[str]:
    """Same call as prose_completion, yielding text deltas as they arrive.

    The lane fallback is narrower than the non-streaming one on purpose: once a
    delta has been handed to the caller it is already on someone's screen, so
    retrying on the other lane would replay a different answer over a partial
    one. Only a failure *before* the first delta falls back; after that the
    error propagates and the caller's generation_failed handling takes over.
    """
    payload = [{"role": "system", "content": system}] + messages
    extra = {"temperature": 0} if settings.prose_provider is not None else {}
    started = False
    try:
        stream = get_client("prose").chat.completions.create(
            model=settings.resolved_prose_model,
            max_tokens=max_tokens,
            messages=payload,
            stream=True,
            **extra,
        )
        for chunk in stream:
            text = _delta_text(chunk)
            if text:
                started = True
                yield text
        return
    except Exception:
        if started or settings.prose_provider is None:
            raise  # mid-answer, or same provider on both lanes — nothing to retry
        logger.exception("prose lane stream failed; falling back to the json lane")

    stream = get_client("json").chat.completions.create(
        model=settings.resolved_chat_model,
        max_tokens=max_tokens,
        messages=payload,
        stream=True,
    )
    for chunk in stream:
        text = _delta_text(chunk)
        if text:
            yield text


def _delta_text(chunk) -> str:
    """Pulls the text out of one streamed chunk. Providers send keep-alive and
    role-only chunks with no content, and a final chunk with no choices at all."""
    if not getattr(chunk, "choices", None):
        return ""
    return getattr(chunk.choices[0].delta, "content", None) or ""
