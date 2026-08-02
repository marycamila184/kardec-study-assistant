import datetime
import json
import os
import random

from src.parsing.chunking import join_subchunks
from src.parsing.cleaner import clean_markdown
from src.parsing.parser import parse_md_to_json

EVANGELHO_BOOK = "O Evangelho Segundo o Espiritismo"
TRECHO_DIARIO_PATH = "data/markdown_files/trecho_diario.md"
CHAPTER_SUMMARIES_PATH = "data/chapter_summaries/evangelho.json"

_chunks: list[dict] | None = None
_summaries: dict[str, str] | None = None


def _get_chunks() -> list[dict]:
    global _chunks
    if _chunks is None:
        with open(TRECHO_DIARIO_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
        _chunks = parse_md_to_json(clean_markdown(raw_text), EVANGELHO_BOOK)
    return _chunks


def _chapter_summaries() -> dict[str, str]:
    global _summaries
    if _summaries is None:
        if os.path.exists(CHAPTER_SUMMARIES_PATH):
            with open(CHAPTER_SUMMARIES_PATH, "r", encoding="utf-8") as f:
                _summaries = json.load(f)
        else:
            _summaries = {}
    return _summaries


def _passages(chunks: list[dict]) -> list[list[dict]]:
    """Every servable passage, one entry per item, in a stable order.

    Stable because the rotation indexes into this list: the order has to be the
    same on every process and every day, so it is sorted by (chapter, item)
    rather than left in whatever order the file was parsed in.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for c in chunks:
        key = (c.get("chapter_title") or "", c.get("item_number") or "")
        grouped.setdefault(key, []).append(c)
    return [
        sorted(grouped[k], key=lambda c: c.get("subchunk_index", 0))
        for k in sorted(grouped)
    ]


# The reading order, fixed once. Every cycle walks the same permutation, which
# is what makes the spacing a guarantee rather than an average: two showings of
# a passage are always exactly one full cycle apart — 109 days on the current
# file — and every passage is served before any repeats.
#
# Reshuffling per cycle was tried first and rejected. It leaves the seam between
# cycles unguarded, so a passage can close one and open the next: measured, a
# repeat three days apart. Guarding the seam by rejecting a colliding shuffle
# does not work either, because a cycle cannot know whether ITS predecessor was
# also reshuffled without walking the whole chain back. The variety was not
# worth a spacing that degrades to three days; a lectionary is a fixed order,
# and this is a lectionary.
_ORDER_SEED = 0


def _select_passage(chunks: list[dict], day: datetime.date) -> dict:
    """The passage for one day, drawn WITHOUT replacement.

    Choosing a chapter and then an item inside it made a passage's odds depend
    on how many items its chapter had. Five chapters of trecho_diario.md hold a
    single item, so those came up ten times more often than items in the
    ten-item chapter: simulated over a year, 73% of days repeated a passage,
    the two most frequent appeared 18 times each, and 12 of the 109 curated
    passages were never served at all.

    Drawing uniformly would not have fixed it — 109 passages over 365 draws
    still collide on ~71% of days. So the day indexes into a fixed permutation
    instead: every passage is served exactly once before any repeats, and two
    showings of the same passage are always one whole cycle apart.
    """
    passages = _passages(chunks)
    order = list(range(len(passages)))
    random.Random(_ORDER_SEED).shuffle(order)
    item_chunks = passages[order[day.toordinal() % len(passages)]]

    first = item_chunks[0]
    return {
        "content": join_subchunks(
            (c["content"], c.get("starts_paragraph", True)) for c in item_chunks
        ),
        "source": {
            "book": EVANGELHO_BOOK,
            "chapter": first.get("chapter"),
            "chapter_title": first.get("chapter_title"),
            "item_number": first.get("item_number"),
            "total_subchunks": first.get("total_subchunks", len(item_chunks)),
        },
    }


def get_daily_passage() -> dict | None:
    try:
        chunks = _get_chunks()
    except OSError:
        return None
    if not chunks:
        return None
    today = datetime.date.today()
    result = _select_passage(chunks, today)
    result["date"] = today.isoformat()
    result["chapter_summary"] = _chapter_summaries().get(
        result["source"]["chapter_title"]
    )
    return result
