"""The single seam every embedding passes through.

`encode()` has three consumers — the ingestion pipeline (offline, whole corpus),
the retriever (one short query per request) and `groundedness.attribute_sources`
(prose lane only, currently off). Keeping the dispatch here means the hosted
lane is a configuration change rather than an edit to any of them.
"""

import huggingface_hub
from sentence_transformers import SentenceTransformer

from src.core.config import EMBEDDING_PROVIDERS, settings

_model: SentenceTransformer | None = None

# Conservative: the providers do not publish a batch ceiling, and the only
# caller that sends more than one text at a time is the offline pipeline, where
# a few extra round trips cost nothing.
HOSTED_BATCH_MAX = 100


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        if settings.hf_token:
            huggingface_hub.login(token=settings.hf_token, add_to_git_credential=False)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _hosted_client():
    from openai import OpenAI

    try:
        base_url, key_field = EMBEDDING_PROVIDERS[settings.embedding_provider]
    except KeyError:
        raise ValueError(
            f"Unknown embedding provider {settings.embedding_provider!r}; "
            f"valid options: {', '.join(EMBEDDING_PROVIDERS)}"
        )
    key = getattr(settings, key_field)
    if not key:
        raise ValueError(
            f"embedding provider {settings.embedding_provider!r} requires "
            f"{key_field.upper()} to be set in the environment/.env"
        )
    return OpenAI(api_key=key, base_url=base_url)


def _encode_hosted(texts: list[str]) -> list[list[float]]:
    """Same model, over HTTP.

    Fails loudly on purpose. A wrong vector raises nothing downstream — Chroma
    stores it happily and retrieval simply gets worse — so a swallowed error
    here would surface weeks later as "the answers got vaguer".
    """
    client = _hosted_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), HOSTED_BATCH_MAX):
        batch = texts[start : start + HOSTED_BATCH_MAX]
        response = client.embeddings.create(model=settings.embedding_model, input=batch)
        returned = [d.embedding for d in response.data]
        if len(returned) != len(batch):
            raise RuntimeError(
                f"a API devolveu {len(returned)} vetores para {len(batch)} textos"
            )
        vectors.extend(returned)
    return vectors


def encode(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider:
        return _encode_hosted(texts)
    return _get_model().encode(texts, convert_to_numpy=True).tolist()
