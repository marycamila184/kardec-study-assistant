import logging
import re

from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

logger = logging.getLogger(__name__)

EVANGELHO_BOOK = "O Evangelho Segundo o Espiritismo"
CHAPTER_COMMENTARY_CAP = 3000  # chars

SENSITIVE_CHAPTERS = frozenset(
    {
        "SUICIDAS",
        "ESPÍRITOS SOFREDORES",
        "ESPÍRITOS ENDURECIDOS",
        "CRIMINOSOS ARREPENDIDOS",
        "EXPIAÇÕES TERRESTRES",
    }
)

_store: VectorStore | None = None

_FOOTNOTE_MARKER = re.compile(r"\n\[Nota \d+\] ")


def has_real_item_number(item_number: str | None) -> bool:
    """False for the parser's fallback placeholder ids (e.g. "section-3"),
    assigned to unnumbered content like a chapter's preamble. These are
    internal bookkeeping only — never a citation a reader would recognize —
    so callers should omit them from anything shown to the LLM or the user.
    """
    return bool(item_number) and not item_number.startswith("section-")


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


def retrieve(
    query: str, top_k: int | None = None, book_filter: str | None = None
) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k
    embedding = encode([query])[0]
    where = {"book": {"$eq": book_filter}} if book_filter else None
    results = _get_store().query(embedding, n_results=top_k, where=where)
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


def retrieve_by_chapter(book: str, chapter: str) -> list[dict]:
    """All chunks of a chapter (footnotes stripped), ordered by
    (item_number, subchunk_index). item_number sorts numerically; the parser's
    'section-N' placeholders sort after the numbered items."""
    results = _get_store().get_by_filter(
        {"$and": [{"book": {"$eq": book}}, {"chapter": {"$eq": chapter}}]}
    )
    results = _strip_footnotes_from_results(results)

    def _key(r: dict):
        item = r["metadata"].get("item_number") or ""
        sub = r["metadata"].get("subchunk_index") or 0
        return (0, int(item), sub) if item.isdigit() else (1, 0, sub)

    return sorted(results, key=_key)


def chapter_commentary(
    book: str,
    chapter: str,
    exclude_item_number: str,
    char_cap: int = CHAPTER_COMMENTARY_CAP,
) -> list[dict]:
    """The chapter's sibling chunks (excluding `exclude_item_number`), in chapter
    order, accumulated until `char_cap` chars. Evangelho-only: the verse+commentary
    split is unique to it. Returns [] for other books, a falsy chapter, or when no
    siblings exist. The first sibling is always included even if it alone exceeds
    the cap (never drop the commentary to empty)."""
    if book != EVANGELHO_BOOK or not chapter:
        return []
    siblings = [
        c
        for c in retrieve_by_chapter(book, chapter)
        if c["metadata"].get("item_number") != exclude_item_number
    ]
    selected: list[dict] = []
    total = 0
    for c in siblings:
        if selected and total + len(c["content"]) > char_cap:
            break
        selected.append(c)
        total += len(c["content"])
    return selected


def _dedup_key(chunk: dict) -> tuple:
    m = chunk["metadata"]
    return (m.get("book"), m.get("item_number"), m.get("subchunk_index"))


def append_chapter_commentary(passages: list[dict]) -> list[dict]:
    """When the first passage is an Evangelho chunk with a chapter, append that
    chapter's bounded Kardec commentary (deduped) so a gospel passage never
    travels without its doctrinal reading. No-op otherwise. Best-effort: a
    retrieval failure logs and returns the passages unchanged."""
    if not passages:
        return passages
    top = passages[0]["metadata"]
    if top.get("book") != EVANGELHO_BOOK or not top.get("chapter"):
        return passages
    try:
        commentary = chapter_commentary(
            top["book"], top["chapter"], top.get("item_number", "")
        )
    except Exception:
        logger.exception("chapter_commentary failed; skipping enrichment")
        return passages
    seen = {_dedup_key(c) for c in passages}
    for c in commentary:
        if _dedup_key(c) not in seen:
            passages.append(c)
            seen.add(_dedup_key(c))
    return passages


def filter_sensitive_chunks(chunks: list[dict]) -> list[dict]:
    """Drop chunks whose chapter_title is one of the darkest testimony chapters of
    O Céu e o Inferno (SENSITIVE_CHAPTERS). Applied only on 'abalo' turns, so
    distressing accounts don't surface for an emotionally vulnerable reader."""
    return [
        c
        for c in chunks
        if c["metadata"].get("chapter_title") not in SENSITIVE_CHAPTERS
    ]
