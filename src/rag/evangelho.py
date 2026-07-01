import datetime
import random

from src.parsing.cleaner import clean_markdown
from src.parsing.parser import parse_md_to_json

EVANGELHO_BOOK = "O Evangelho Segundo o Espiritismo"
TRECHO_DIARIO_PATH = "data/markdown_files/trecho_diario.md"

_chunks: list[dict] | None = None


def _get_chunks() -> list[dict]:
    global _chunks
    if _chunks is None:
        with open(TRECHO_DIARIO_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
        _chunks = parse_md_to_json(clean_markdown(raw_text), EVANGELHO_BOOK)
    return _chunks


def _select_passage(chunks: list[dict], seed: str) -> dict:
    rng = random.Random(seed)

    chapters: dict[str, list[dict]] = {}
    for c in chunks:
        chapter = c.get("chapter_title") or "__no_chapter__"
        chapters.setdefault(chapter, []).append(c)
    chapter_chunks = chapters[rng.choice(sorted(chapters))]

    items: dict[str, list[dict]] = {}
    for c in chapter_chunks:
        item = c.get("item_number") or "__no_item__"
        items.setdefault(item, []).append(c)
    item_chunks = sorted(
        items[rng.choice(sorted(items))], key=lambda c: c.get("subchunk_index", 0)
    )

    first = item_chunks[0]
    return {
        "content": " ".join(c["content"] for c in item_chunks),
        "source": {
            "book": EVANGELHO_BOOK,
            "chapter": first.get("chapter"),
            "chapter_title": first.get("chapter_title"),
            "item_number": first.get("item_number"),
            "total_subchunks": first.get("total_subchunks", len(item_chunks)),
        },
    }


def get_daily_passage() -> dict | None:
    chunks = _get_chunks()
    if not chunks:
        return None
    today = datetime.date.today().isoformat()
    result = _select_passage(chunks, today)
    result["date"] = today
    return result
