"""The day's passage explanation, cached for one day.

`streamStudy` takes no profile and no history: the answer is entirely
determined by the passage, so it is identical for every reader that day.
Without a cache, that costs one LLM call per reader to produce the same
text.

This is NOT model prose outside the guards, in the sense CLAUDE.md forbids.
There, the prose came through another path, with no guard at all. Here it is
the same /study pipeline, with max_distance and find_unsupported_quotes
running as always — once instead of N times — and it lives for one day, not
years. See
docs/superpowers/specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md

A separate collection from the subscriptions one, and never crossed with it:
what is here is the same reflection for everyone, with nothing of anyone's.
"""

import logging
from hashlib import sha256

from src.core.config import settings
from src.core.firestore import client

logger = logging.getLogger(__name__)


def cache_key(passage: dict) -> str:
    """The passage's identity plus the date — never the date alone.

    Keying by date alone would serve stale text after a correction to
    data/markdown_files/trecho_diario.md, and that file is hand-curated
    precisely because it gets corrected.
    """
    s = passage.get("source", {})
    cru = "|".join(
        str(x)
        for x in (
            passage.get("date"),
            s.get("book"),
            s.get("chapter"),
            s.get("part"),
            s.get("item_number"),
        )
    )
    return sha256(cru.encode()).hexdigest()


def _colecao():
    return client().collection(settings.reflection_collection)


def get(passage: dict) -> dict | None:
    """The cached explanation, or None. Never raises.

    The cache is a saving, not a dependency: if Firestore is down, the
    reader waits for the stream, as they do today.
    """
    try:
        doc = _colecao().document(cache_key(passage)).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("answer")
    except Exception:
        logger.exception("failed to read the reflection cache")
        return None


def put(passage: dict, answer: dict) -> None:
    """Stores the day's explanation. Never raises.

    Whoever calls this is responsible for NEVER calling it with a failure:
    an answer withheld by find_unsupported_quotes, or a generation_failed,
    stored here would be served to the whole day.
    """
    try:
        _colecao().document(cache_key(passage)).set({"answer": answer})
    except Exception:
        logger.exception("failed to write the reflection cache")
