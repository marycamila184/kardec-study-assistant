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

    An identity may legitimately omit `chapter` or `part`, because whether they
    are needed is a property of the book. Numbering restarts per chapter only in
    Evangelho, Céu e Inferno and A Gênese — and per *part* again in Céu e
    Inferno. In O Livro dos Espíritos the questões run 1-1019 without repeating,
    so the curated trilhas name book + item alone and that identity is complete.

    So an omitted field means "unspecified", and the rule is: **an
    under-specified identity resolves only when it is unambiguous.** One match
    is returned; several raise `AmbiguousPassage`. That keeps the property this
    function exists for — a static page written once and served for years must
    never silently glue two different passages together — without rejecting the
    identities the corpus makes complete.
    """
    exact = index.get(_key(book, chapter, item_number, part))
    if exact:
        return join_subchunks(
            (c["content"], c.get("starts_paragraph", True)) for c in exact
        )

    item = str(item_number)
    matches = [
        (key, chunks)
        for key, chunks in index.items()
        if key[0] == book
        and key[2] == item
        and (chapter is None or key[1] == chapter)
        and (part is None or key[3] == part)
    ]
    if not matches:
        raise PassageNotFound(
            f"{book} / chapter={chapter} / item {item_number} / part={part}"
        )
    if len(matches) > 1:
        found = "; ".join(
            f"chapter={k[1]!r} part={k[3]!r}" for k, _ in sorted(matches, key=str)
        )
        raise AmbiguousPassage(
            f"{book} / item {item_number} matches {len(matches)} passages "
            f"({found}) — name the chapter and part."
        )
    return join_subchunks(
        (c["content"], c.get("starts_paragraph", True)) for c in matches[0][1]
    )
