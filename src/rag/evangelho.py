import datetime
import random

from src.rag.retriever import _get_store

EVANGELHO_BOOK = "O Evangelho Segundo o Espiritismo"


def get_daily_passage() -> dict | None:
    chunks = _get_store().get_by_filter({"book": {"$eq": EVANGELHO_BOOK}})
    if not chunks:
        return None

    today = datetime.date.today().isoformat()
    rng = random.Random(today)

    # Group chunks by chapter
    chapters: dict[str, list] = {}
    for c in chunks:
        chapter = c["metadata"].get("chapter_title") or "__no_chapter__"
        chapters.setdefault(chapter, []).append(c)

    # Pick a random chapter, then a random item within it, then subchunk_index 0
    chapter_key = rng.choice(sorted(chapters))
    chapter_chunks = chapters[chapter_key]

    items: dict[str, list] = {}
    for c in chapter_chunks:
        item = c["metadata"].get("item_number") or "__no_item__"
        items.setdefault(item, []).append(c)

    item_key = rng.choice(sorted(items))
    item_chunks = sorted(items[item_key], key=lambda c: c["metadata"].get("subchunk_index", 0))
    chunk = item_chunks[0]
    meta = chunk["metadata"]
    return {
        "date": today,
        "content": chunk["content"],
        "source": {
            "book": EVANGELHO_BOOK,
            "chapter": meta.get("chapter"),
            "chapter_title": meta.get("chapter_title"),
            "item_number": meta.get("item_number"),
            "subchunk_index": meta.get("subchunk_index"),
            "total_subchunks": meta.get("total_subchunks"),
        },
    }
