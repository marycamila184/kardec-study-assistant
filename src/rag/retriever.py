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

# Reflect grounds only in the two reflection-appropriate works: broad moral
# doctrine (Espíritos) and practical guidance for living (Evangelho). This keeps
# O Céu e o Inferno's afterlife testimony, A Gênese's cosmology, and O Livro dos
# Médiuns' mediumship technique out of life-situation reflections — a register
# fix, independent of the abalo/sensitivity layer.
REFLECT_BOOKS: tuple[str, str] = (
    "O Livro dos Espíritos",
    "O Evangelho Segundo o Espiritismo",
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


def item_word(book: str) -> str:
    """What a numbered entry is *called* in a given work, for passage headers
    fed to the LLM.

    O Livro dos Espíritos numbers questões; the other four number itens. The
    header is the only place the model learns this vocabulary, so labelling an
    LE passage "Item 341" produced prose that said "o Item 341 do Livro dos
    Espíritos" while the source chip beside it said "Q.341" — two names for one
    passage on the same screen. The frontend's formatItemRef() is the display
    half of this same rule.
    """
    return "Questão" if book == "O Livro dos Espíritos" else "Item"


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
    query: str,
    top_k: int | None = None,
    book_filter: str | list[str] | None = None,
) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k
    embedding = encode([query])[0]
    if isinstance(book_filter, str):
        where = {"book": {"$eq": book_filter}}
    elif book_filter:
        where = {"book": {"$in": list(book_filter)}}
    else:
        where = None
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


# Suicide-adjacent passages exist outside the dark testimony chapters too —
# e.g. ESE's afflictions chapter discussing "abreviar as misérias" / "morte
# voluntária". On an abalo turn these must not be introduced to someone who
# never raised the theme, whatever book they come from.
_SENSITIVE_CONTENT_RE = re.compile(
    r"suic[ií]d"
    r"|abreviar (?:a vida|as mis[ée]rias|suas mis[ée]rias|os dias)"
    r"|morte volunt[áa]ria",
    re.IGNORECASE,
)


def filter_sensitive_chunks(chunks: list[dict]) -> list[dict]:
    """Drop chunks whose chapter_title is one of the darkest testimony chapters
    of O Céu e o Inferno (SENSITIVE_CHAPTERS), plus any chunk whose content
    matches suicide-adjacent language (_SENSITIVE_CONTENT_RE) regardless of
    book. Applied only on 'abalo' turns, so distressing material never
    surfaces unprompted for an emotionally vulnerable reader."""
    return [
        c
        for c in chunks
        if c["metadata"].get("chapter_title") not in SENSITIVE_CHAPTERS
        and not _SENSITIVE_CONTENT_RE.search(c["content"])
    ]


def filter_uncitable_chunks(chunks: list[dict]) -> list[dict]:
    """Drops chunks with no item number — text nobody can look up.

    Two thirds of O Céu e o Inferno is spirit testimony rather than doctrinal
    exposition, and the parser numbers none of it: 65% of that book's chunks
    against 0-12% everywhere else.

    They are removed for two reasons that point the same way. A chunk with no
    number cannot become a usable citation — the source chip reads "cap. VIII"
    with nothing to look up, which is the opposite of what a study companion
    owes a reader. And testimony is personal language, so it wins on similarity
    exactly when the message is personal and loses on usefulness: on 2026-07-28,
    "não posso fazer fofoca sobre o meu irmão" retrieved "não ter sido esquecido
    entre os meus irmãos espíritas" and produced an answer about collective
    calamities.

    Measured before adopting (scripts/probe_unnumbered_chunks.py): on ordinary
    doctrine only 10% of retrieved chunks are unnumbered and nothing is lost; on
    personal messages it is 70%; and on the questions only the doctrinal half of
    Céu e Inferno answers — the future life, the penalties, expiation — not one
    is emptied, because the numbered items still rank.

    The consequence to know: a message that retrieves ONLY testimony now
    retrieves nothing, and the reader gets "não encontrei" instead of an answer.
    For "estou preocupado com meu pai que está doente" that is the honest
    outcome — it is the Refletir case, which this project already decided
    retrieval answers badly.

    Deliberately NOT applied to retrieve_by_item or retrieve_by_chapter: someone
    studying a chapter should see all of it, testimony included. This is about
    what the system offers unprompted.
    """
    return [c for c in chunks if str(c["metadata"].get("item_number", "")).isdigit()]
