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
