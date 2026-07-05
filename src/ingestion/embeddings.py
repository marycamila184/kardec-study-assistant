import huggingface_hub
from sentence_transformers import SentenceTransformer

from src.core.config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        if settings.hf_token:
            huggingface_hub.login(token=settings.hf_token, add_to_git_credential=False)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    return _get_model().encode(texts, convert_to_numpy=True).tolist()
