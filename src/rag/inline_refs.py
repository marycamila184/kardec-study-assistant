"""Inline grounding markers: where in a sentence a claim rests on a passage.

The answer that prompted this said "o comentário doutrinário de Allan Kardec
sobre este capítulo destaca a importância…" and gave the reader no way to open
what it cited. The items had been retrieved and fed to the prompt; they were
simply never returned.

Two vocabularies, because the two agents number things differently. /chat
retrieves across books, where a bare item number is ambiguous — the same
ambiguity that forces Curador to carry `chapter` — so it marks the passage index
its prompt already prints. /study works inside one chapter, where the item
number is what a reader looks up in their own copy.

**A marker naming something that was not retrieved is dropped**, leaving the
prose intact. An inline citation is an invitation to verify, so a fabricated one
is worse than none: it survives exactly as long as it takes someone to check it,
and the reader most likely to check is the teacher building a class around it.

Markers never reach the screen. They are parsed out into positions on the clean
text, so a client that ignores `inline_refs` displays what it displays today.

See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
"""

import re

# "[item 11]", "[ITEM 11]", "[item11]" — the mangling worth tolerating, and no
# more. A bare "[11]" is NOT an item marker: /study prose legitimately contains
# bracketed numbers, and guessing would strip a reader's own text.
_ITEM_MARKER = re.compile(r"\[\s*item\s*(\d{1,4})\s*\]", re.IGNORECASE)

# "[fonte 1]", "[FONTE 1, 3]" — the passage indices /chat's prompt prints.
#
# The word is load-bearing, not decoration. A bare "[1]" would collide with
# brackets that occur in ordinary prose and in the works themselves, and it
# would be a third silent vocabulary for a concept the system already names
# twice: the "[FONTES: 1, 3]" trailer and the "Fonte citada" modal. It also
# degrades better — every guard can fail, and a stray "[fonte 1]" on screen
# reads as a clumsy citation while a stray "[1]" reads as a bug.
_PASSAGE_MARKER = re.compile(
    r"\[\s*fontes?\s*(\d{1,2}(?:\s*[,\s]\s*\d{1,2})*)\s*\]", re.IGNORECASE
)


def extract_item_refs(text: str, allowed: list[dict]) -> tuple[str, list[dict]]:
    """Pulls `[item N]` out of /study prose.

    `allowed` is the retrieved chapter context — each entry carrying `book`,
    `chapter_title`, `item_number` and `excerpt`. Markers naming anything else
    are removed without a trace.

    Returns (clean_text, refs), where each ref carries `position`: the index
    into clean_text where the marker stood.
    """
    by_item = {str(a["item_number"]): a for a in allowed}

    def _resolve(number: str) -> list[dict]:
        found = by_item.get(number)
        return [found] if found else []

    return _extract(text, _ITEM_MARKER, _resolve)


def extract_passage_refs(text: str, chunks: list[dict]) -> tuple[str, list[dict]]:
    """Pulls `[N]` out of /chat prose, where N is the 1-based passage index the
    prompt printed. Indices outside the retrieved list are removed."""

    def _resolve(body: str) -> list[dict]:
        out = []
        for part in re.split(r"[,\s]+", body.strip()):
            if not part.isdigit():
                continue
            index = int(part)
            if 1 <= index <= len(chunks):
                meta = chunks[index - 1]["metadata"]
                out.append(
                    {
                        "book": meta["book"],
                        "chapter_title": meta.get("chapter_title") or None,
                        "item_number": meta.get("item_number"),
                        "excerpt": chunks[index - 1]["content"],
                    }
                )
        return out

    return _extract(text, _PASSAGE_MARKER, _resolve)


# A private-use codepoint, which cannot occur in the works or in model prose.
# Each resolved marker leaves one behind so its position survives the whitespace
# tidying below; positions computed before that cleanup would drift by however
# much it removed.
_SENTINEL = "\ue000"


def _extract(text: str, pattern: re.Pattern, resolve) -> tuple[str, list[dict]]:
    """Shared walk: rebuild the text without markers, recording where each
    resolved one stood.

    Position is measured on the clean text, so a client can use it directly
    against what it displays, and it attaches to the end of the preceding word —
    a reference belongs to the clause before it, not to the one after.
    """
    if not text:
        return text, []

    parts: list[str] = []
    refs: list[dict] = []
    last = 0

    for match in pattern.finditer(text):
        parts.append(text[last : match.start()])
        resolved = resolve(match.group(1))
        if resolved:
            parts.append(_SENTINEL)
            refs.extend(resolved)
        # Unresolved markers vanish exactly like resolved ones: the reader never
        # sees a bracket either way, and a dropped reference must not leave a
        # scar suggesting something was removed.
        last = match.end()

    parts.append(text[last:])
    marked = "".join(parts)

    # A marker sitting between a word and its punctuation leaves a stray space
    # behind ("progresso [item 5]." -> "progresso ."). Not cosmetic: these
    # answers get read aloud in classes and pasted into handouts.

    marked = re.sub(" +" + _SENTINEL, _SENTINEL, marked)
    marked = re.sub(
        _SENTINEL + r" +([,.;:!?])", lambda m: _SENTINEL + m.group(1), marked
    )
    marked = re.sub(r" +([,.;:!?])", r"\1", marked)
    marked = re.sub(r"[ \t]{2,}", " ", marked)

    clean_parts: list[str] = []
    positions: list[int] = []
    length = 0
    for i, segment in enumerate(marked.split(_SENTINEL)):
        clean_parts.append(segment)
        length += len(segment)
        if i < len(refs):
            positions.append(length)

    clean = "".join(clean_parts)
    return clean, [{**ref, "position": pos} for ref, pos in zip(refs, positions)]


class InlineMarkerFilter:
    """Strips inline markers from a stream without ever emitting a partial one.

    Built for a marker vocabulary — "item" for /study, "fonte" for /chat — so
    the two lanes share the mechanism and differ only in the word.

    The trailer buffer in stream_buffer.py cannot do this job: it *seals* on the
    first opening, because a trailer is terminal by contract. Inline markers sit
    in the middle of prose, so sealing would swallow the rest of the answer.
    This one holds only the candidate and resumes.

    Markers are dropped rather than forwarded because the reader never sees them
    in the finished answer either — `done` carries the clean text plus the
    resolved references, and the streamed text has to end up identical to it.
    """

    # Longest hold: "[ fontes 1, 3" plus slack, before a "]" is required. A
    # candidate that outgrows this was never a marker, and holding prose
    # indefinitely would be worse than showing a bracket.
    _MAX_HOLD = 20

    def __init__(self, word: str = "item") -> None:
        # The leading space is consumed with the marker, matching the tidying
        # the extractors do. Without it the stream shows "progredir ." for the
        # instant before `done` replaces the text, and the streamed answer would
        # not be character-identical to the one that stands.
        self._full = re.compile(
            r"[ \t]*\[\s*%ss?\s*(\d{1,4}(?:\s*[,\s]\s*\d{1,4})*)\s*\]" % word,
            re.IGNORECASE,
        )
        # Every prefix of the word, so a marker split anywhere is still caught.
        prefixes = "".join(f"({c}" for c in word) + ")?" * len(word)
        self._partial = re.compile(
            r"[ \t]*\[\s*(?:%s)?s?[\d,\s]{0,12}$" % prefixes, re.IGNORECASE
        )
        self._held = ""

    def feed(self, chunk: str) -> str:
        """Returns the text safe to show now; holds anything that might still
        become a marker."""
        pending = self._full.sub("", self._held + chunk)

        match = self._partial.search(pending)
        if match and len(pending) - match.start() <= self._MAX_HOLD:
            self._held = pending[match.start() :]
            return pending[: match.start()]

        self._held = ""
        return pending

    def flush(self) -> str:
        """What is still held when the stream ends — a marker that never closed
        is prose after all, and withholding it would silently truncate the
        answer."""
        held, self._held = self._held, ""
        return self._full.sub("", held)
