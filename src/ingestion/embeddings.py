"""The single seam every embedding passes through.

`encode()` has three consumers — the ingestion pipeline (offline, whole corpus),
the retriever (one short query per request) and `groundedness.attribute_sources`
(prose lane only, currently off). Keeping the dispatch here means the hosted
lane is a configuration change rather than an edit to any of them.
"""

import logging
import time
from typing import Any

from src.core.config import EMBEDDING_PROVIDERS, settings

logger = logging.getLogger(__name__)

# Seam, so a test can move the clock without touching the module's imports.
_now = time.monotonic

# sentence_transformers pulls torch, and torch is most of the container image.
# Importing it lazily is what lets a hosted-only deployment drop the dependency
# entirely instead of shipping ~2.3 GB of weights plus the framework to load
# them — which is the whole point of the hosted lane. Module-level imports here
# would keep the image fat no matter what EMBEDDING_PROVIDER says.
_model: Any = None

# Conservative: the providers do not publish a batch ceiling, and the only
# caller that sends more than one text at a time is the offline pipeline, where
# a few extra round trips cost nothing.
HOSTED_BATCH_MAX = 100

# The bound on one hosted call, and why it is not a single number.
#
# Measured against OpenRouter on 2026-08-03, single-query calls: 0.39, 0.45,
# 1.07, 1.33, 1.42, 1.48, 1.55, 1.84, 1.89, 2.07, 2.15 — and 31.85, 32.20,
# 110.91. Roughly one call in five hangs, and the openai SDK default is a 600s
# read timeout with 2 retries, so one hang can hold a request for far longer
# than the 120s Cloud Run allows it. The retry is what actually recovers: the
# hang is not the provider being slow, it is one request going nowhere.
#
# The budget scales with the batch because the two callers are not comparable.
# The retriever sends ONE short query and a reader is waiting; the ingestion
# pipeline sends batches of up to HOSTED_BATCH_MAX and nobody is. A single
# budget either strangles the corpus pass or lets a request hang.
HOSTED_TIMEOUT_BASE_S = 6.0
HOSTED_TIMEOUT_PER_TEXT_S = 0.5
HOSTED_MAX_RETRIES = 2


def _hosted_timeout(n_texts: int) -> float:
    """~6.5s for one query, ~56s for a full ingestion batch."""
    return HOSTED_TIMEOUT_BASE_S + HOSTED_TIMEOUT_PER_TEXT_S * n_texts


def _get_model() -> Any:
    global _model
    if _model is None:
        import huggingface_hub
        from sentence_transformers import SentenceTransformer

        if settings.hf_token:
            huggingface_hub.login(token=settings.hf_token, add_to_git_credential=False)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _new_openai(**kwargs):
    """The one place the SDK client is constructed, so a test can watch it."""
    from openai import OpenAI

    return OpenAI(**kwargs)


def _require(provider: str) -> tuple[str, str, str]:
    try:
        entry = EMBEDDING_PROVIDERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown embedding provider {provider!r}; "
            f"valid options: {', '.join(EMBEDDING_PROVIDERS)}"
        )
    if not getattr(settings, entry[1], None):
        raise ValueError(
            f"embedding provider {provider!r} requires "
            f"{entry[1].upper()} to be set in the environment/.env"
        )
    return entry


def _provider_chain() -> list[str]:
    """The configured provider, then any other that could stand in for it.

    A fallback has to serve **the same model**. Parity was measured for bge-m3
    against the stored vectors (cosine 0.999994, 2026-07-27), and that is what
    makes the hosted lane safe at all; a provider serving anything else would
    put queries in a different space, and nothing downstream would say so —
    Chroma stores whatever it is given and retrieval merely gets worse.

    A provider with no key configured is not a fallback, it is a 401.
    """
    primary = settings.embedding_provider
    _, _, model_id = _require(primary)
    chain = [primary]
    for name, (_, key_field, other_model) in EMBEDDING_PROVIDERS.items():
        if name == primary:
            continue
        if other_model.lower() != model_id.lower():
            continue
        if getattr(settings, key_field, None):
            chain.append(name)
    return chain


def _hosted_client(provider: str, timeout: float):
    base_url, key_field, _ = _require(provider)
    return _new_openai(
        api_key=getattr(settings, key_field),
        base_url=base_url,
        timeout=timeout,
        max_retries=HOSTED_MAX_RETRIES,
    )


def _hosted_model_id(provider: str | None = None) -> str:
    return EMBEDDING_PROVIDERS[provider or settings.embedding_provider][2]


# The providers that are themselves routers, and so understand a routing block.
# `baai/bge-m3` on OpenRouter sits behind two upstreams — DeepInfra and Parasail
# (verified 2026-08-03) — and by default it spreads across them. DeepInfra and
# Novita ARE upstreams: `provider` is not their vocabulary, and an unknown body
# key is at best ignored and at worst a 400.
_ROUTED_PROVIDERS = {"openrouter"}

# Above this, one call is worth a line someone will actually see. Production
# logs at INFO, so a DEBUG line never arrives — and the call worth correlating
# is precisely the slow one.
SLOW_CALL_S = 10.0


def _routing_extra(provider: str) -> dict:
    """`sort: latency` asks OpenRouter to prefer its faster upstream rather than
    spread across them. Fallback stays on: this expresses a preference, and the
    point of routing through an aggregator is that it can still move.
    """
    if provider not in _ROUTED_PROVIDERS:
        return {}
    return {"extra_body": {"provider": {"sort": "latency"}}}


def _served_by(response: Any) -> str:
    """Which upstream actually answered, when the provider says so.

    OpenRouter reports it, and throwing it away is why the hangs of 2026-08-03
    could not be pinned on either of the two candidates. Never worth an
    exception: this is diagnostics.
    """
    try:
        return response.model_dump().get("provider") or "unreported"
    except Exception:
        return "unreported"


def _embed_batch(batch: list[str], chain: list[str]) -> list[list[float]]:
    """One batch, trying each provider in turn.

    Only *transport* failures move to the next host. A response with the wrong
    number of vectors is a correctness fault — it misaligns every id in the
    batch — and retrying that elsewhere would hide it, so it is raised.
    """
    timeout = _hosted_timeout(len(batch))
    last: Exception | None = None
    for provider in chain:
        started = _now()
        try:
            client = _hosted_client(provider, timeout)
            response = client.embeddings.create(
                model=_hosted_model_id(provider),
                input=batch,
                **_routing_extra(provider),
            )
        except Exception as exc:  # transport: timeout, connection, 5xx, 429
            last = exc
            logger.warning(
                "embedding provider %r failed (%s: %s)%s",
                provider,
                type(exc).__name__,
                exc,
                "; trying the next" if provider != chain[-1] else "; none left",
            )
            continue

        elapsed = _now() - started
        served_by = _served_by(response)
        if elapsed >= SLOW_CALL_S:
            logger.warning(
                "slow embedding call: %.1fs for %d text(s) via %s (upstream %s)",
                elapsed,
                len(batch),
                provider,
                served_by,
            )
        else:
            logger.debug(
                "embedding: %d text(s) in %.2fs via %s (upstream %s)",
                len(batch),
                elapsed,
                provider,
                served_by,
            )

        returned = [d.embedding for d in response.data]
        if len(returned) != len(batch):
            raise RuntimeError(
                f"a API devolveu {len(returned)} vetores para {len(batch)} textos"
            )
        if provider != chain[0]:
            logger.warning("embeddings served by the fallback provider %r", provider)
        return returned

    raise RuntimeError(
        f"every embedding provider failed ({', '.join(chain)}); last: {last}"
    ) from last


def _encode_hosted(texts: list[str]) -> list[list[float]]:
    """Same model, over HTTP.

    Fails loudly on purpose. A wrong vector raises nothing downstream — Chroma
    stores it happily and retrieval simply gets worse — so a swallowed error
    here would surface weeks later as "the answers got vaguer".
    """
    chain = _provider_chain()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), HOSTED_BATCH_MAX):
        vectors.extend(_embed_batch(texts[start : start + HOSTED_BATCH_MAX], chain))
    return vectors


def encode(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider:
        return _encode_hosted(texts)
    return _get_model().encode(texts, convert_to_numpy=True).tolist()
