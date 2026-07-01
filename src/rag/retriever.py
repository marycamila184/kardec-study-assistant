import re

from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

_store: VectorStore | None = None

_FOOTNOTE_MARKER = re.compile(r"\n\[Nota \d+\] ")


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return _store


def _split_footnotes(content: str) -> tuple[str, str]:
    """Splits ingestion-baked footnote suffixes off a chunk's content.

    Returns (clean_content, footnote_context) — footnote_context is ""
    when no footnote marker is found.
    """
    match = _FOOTNOTE_MARKER.search(content)
    if not match:
        return content, ""
    return content[: match.start()], content[match.start() + 1 :]


def _strip_footnotes_from_results(results: list[dict]) -> list[dict]:
    for r in results:
        clean, footnotes = _split_footnotes(r["content"])
        r["content"] = clean
        r["footnote_context"] = footnotes
    return results


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k
    embedding = encode([query])[0]
    results = _get_store().query(embedding, n_results=top_k)
    filtered = [r for r in results if r["distance"] <= settings.max_distance]
    return _strip_footnotes_from_results(filtered)


def retrieve_by_item(
    book: str, item_number: str, chapter: str | None = None
) -> list[dict]:
    conditions: list[dict] = [
        {"book": {"$eq": book}},
        {"item_number": {"$eq": item_number}},
    ]
    if chapter is not None:
        conditions.append({"chapter": {"$eq": chapter}})
    results = _get_store().get_by_filter({"$and": conditions})
    return _strip_footnotes_from_results(results)
