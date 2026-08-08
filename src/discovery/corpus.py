"""The committed corpus, indexed for the static page generator.

Reads data/json_files/ — the parser's output, which is committed — so page
generation needs no ChromaDB, no embeddings and no API key. Nothing here is
imported by src/api/; this is build-time only.
"""

import json
import os

from src.parsing.chunking import join_subchunks


class PassageNotFound(Exception):
    """No chunk matches the identity given."""


class AmbiguousPassage(Exception):
    """The identity omits `part` for a key that exists in more than one part."""


def _key(book: str, chapter: str | None, item_number: str, part: str | None) -> tuple:
    return (book, chapter, str(item_number), part)


def load_corpus(json_dir: str) -> dict[tuple, list[dict]]:
    """Every chunk keyed by (book, chapter, item_number, part).

    The four-part key is the same one `_build_id` encodes at ingestion. Using
    book + item alone collides on 14 keys in O Céu e o Inferno.
    """
    index: dict[tuple, list[dict]] = {}
    for filename in sorted(os.listdir(json_dir)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(json_dir, filename), encoding="utf-8") as f:
            for chunk in json.load(f):
                key = _key(
                    chunk["book"],
                    chunk["chapter"],
                    chunk["item_number"],
                    chunk.get("part"),
                )
                index.setdefault(key, []).append(chunk)
    for chunks in index.values():
        # The file's order is not a contract, the same reason retrieve_by_item
        # sorts: subchunk_index is.
        chunks.sort(key=lambda c: c["subchunk_index"])
    return index


def passage_text(
    index: dict[tuple, list[dict]],
    book: str,
    chapter: str | None,
    item_number: str,
    part: str | None = None,
) -> str | None:
    """One passage, rejoined as the source had it.

    `part=None` means "this chunk has no part" — an exact match, NOT the
    "do not filter" that `retrieve_by_item` gives it. A static page is written
    once and served for years, so an under-specified identity has to fail at
    build time instead of quietly rendering two passages as one.
    """
    key = _key(book, chapter, item_number, part)
    chunks = index.get(key)
    if not chunks:
        if part is None:
            parts = sorted(
                str(k[3])
                for k in index
                if k[0] == book and k[1] == chapter and k[2] == str(item_number)
            )
            if parts:
                raise AmbiguousPassage(
                    f"{book} / {chapter} / item {item_number} exists in "
                    f"{len(parts)} parts ({', '.join(parts)}); name one."
                )
        raise PassageNotFound(f"{book} / {chapter} / item {item_number} / part={part}")
    return join_subchunks(
        (c["content"], c.get("starts_paragraph", True)) for c in chunks
    )
