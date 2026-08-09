"""Curated page content: topics (new) and trilhas (already curated).

A topic and a trilha are the same shape — a title, framing prose, and an
ordered list of passage identities — so one loader and one renderer serve
both. Everything a reader sees is either a corpus passage or text a human
wrote in these files. No model writes here.
"""

import json
import os
import re
from dataclasses import dataclass

from src.discovery.corpus import AmbiguousPassage, PassageNotFound, passage_text

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContentError(Exception):
    """A content file is invalid. Always fatal: a bad page must not ship."""


@dataclass(frozen=True)
class Passage:
    book: str
    chapter: str | None
    item_number: str
    part: str | None
    label: str
    text: str


@dataclass(frozen=True)
class Page:
    slug: str
    kind: str  # "tema" | "trilha"
    title: str  # the <title> tag
    heading: str  # the <h1>
    meta_description: str
    intro: str
    passages: list[Passage]


def _require(data: dict, field: str, source: str) -> str:
    value = (data.get(field) or "").strip()
    if not value:
        raise ContentError(f"{source}: '{field}' is required and must not be empty")
    return value


def _resolve(steps: list[dict], index: dict, source: str) -> list[Passage]:
    passages = []
    for position, step in enumerate(steps, start=1):
        where = f"{source} step {position}"
        book = _require(step, "book", where)
        item_number = str(_require(step, "item_number", where))
        chapter = step.get("chapter")
        part = step.get("part")
        try:
            text = passage_text(index, book, chapter, item_number, part)
        except (PassageNotFound, AmbiguousPassage) as exc:
            raise ContentError(f"{where}: {exc}") from exc
        passages.append(
            Passage(
                book=book,
                chapter=chapter,
                item_number=item_number,
                part=part,
                label=step.get("label") or f"Item {item_number}",
                text=text,
            )
        )
    if not passages:
        raise ContentError(f"{source}: no steps")
    return passages


def _slug(data: dict, source: str) -> str:
    """The page's `id`, checked once for both kinds.

    One definition on purpose: when the two kinds each carried their own copy
    of this check, a change to the rule could be made in one and missed in the
    other, and the slug is what the URL is built from.
    """
    slug = _require(data, "id", source)
    if not SLUG.match(slug):
        raise ContentError(f"{source}: 'id' is not a url-safe slug: {slug!r}")
    return slug


def _page_from_topic(data: dict, index: dict, source: str) -> Page:
    slug = _slug(data, source)
    return Page(
        slug=slug,
        kind="tema",
        title=_require(data, "title", source),
        heading=_require(data, "question", source),
        meta_description=_require(data, "meta_description", source),
        intro=_require(data, "intro", source),
        passages=_resolve(data.get("steps", []), index, source),
    )


def _page_from_trilha(data: dict, index: dict, source: str) -> Page:
    slug = _slug(data, source)
    # A trilha has no separate meta_description or intro; `description` is
    # already the one-line summary the app shows, and it serves both here.
    description = _require(data, "description", source)
    title = _require(data, "title", source)
    return Page(
        slug=slug,
        kind="trilha",
        title=f"{title} — Dialogando com a Doutrina",
        heading=title,
        meta_description=description,
        intro=description,
        passages=_resolve(data.get("steps", []), index, source),
    )


def _load_dir(directory: str, index: dict, build) -> list[Page]:
    if not os.path.isdir(directory):
        return []
    pages = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(directory, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        pages.append(build(data, index, filepath))
    return pages


def load_pages(topics_dir: str, paths_dir: str, index: dict) -> list[Page]:
    pages = _load_dir(topics_dir, index, _page_from_topic) + _load_dir(
        paths_dir, index, _page_from_trilha
    )
    # Two sources sharing a slug write to the same directory, so the second
    # silently replaces the first — one curated page vanishes and the sitemap
    # still lists exactly one URL, so nothing downstream can notice.
    seen: dict[tuple[str, str], None] = {}
    for page in pages:
        key = (page.kind, page.slug)
        if key in seen:
            raise ContentError(
                f"duplicate {page.kind} slug {page.slug!r}: two source files "
                f"would write the same page and one would be lost"
            )
        seen[key] = None
    return pages
