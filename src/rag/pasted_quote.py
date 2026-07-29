"""Recognises a passage the reader pasted, and resolves it to its item.

Someone pastes a paragraph and writes "me explique esse". Two things are true
at once: the model cannot discuss text it was never given — `anchor_text` only
biases the search and never enters the prompt — and nobody has checked that the
pasted text is actually Kardec's. Misattributed quotations circulate widely, and
"is this real, and where is it?" is a teacher's question more than a student's.

Both are answered by the same move: retrieve on the pasted text, then verify
that a retrieved passage really is inside what was pasted. If it is, the message
is about a known item, and everything downstream treats it as one — the same
path a question naming "questão 132" already takes.

Verification is containment, not similarity. A passage that merely resembles
the paste is what retrieval returns for everything; a passage whose words are
literally in the message is the one being asked about.

See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md
"""

import re
import unicodedata

# Below this, a match is coincidence: any two Portuguese sentences about the
# spirit share short runs. Twelve consecutive words is a quotation.
MIN_MATCHED_WORDS = 12

# Under this, the message is a question, not a paste — checking every short
# question against every retrieved chunk would find spurious overlaps and cost
# nothing but confusion.
MIN_PASTE_WORDS = 25


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", stripped)).strip()


def find_pasted_source(question: str, chunks: list[dict]) -> dict | None:
    """The retrieved chunk whose text the reader pasted, or None.

    Returns the chunk itself so the caller can hand it on unchanged — the point
    is to reach the ordinary "this question is about a known item" path, not to
    invent a parallel one.
    """
    words = _normalise(question).split()
    if len(words) < MIN_PASTE_WORDS or not chunks:
        return None

    haystack = " ".join(words)
    best = None
    best_len = MIN_MATCHED_WORDS - 1

    for chunk in chunks:
        matched = _longest_run_inside(chunk.get("content", ""), haystack)
        if matched > best_len:
            best, best_len = chunk, matched

    return best


def _longest_run_inside(content: str, haystack: str) -> int:
    """How many consecutive words of `content` appear inside `haystack`.

    Walks the passage rather than the message: the reader may have pasted one
    paragraph of a longer item, or trimmed the ending, and the run that matters
    is the one the passage contributes.
    """
    words = _normalise(content).split()
    if len(words) < MIN_MATCHED_WORDS:
        return 0

    longest = 0
    for start in range(len(words) - MIN_MATCHED_WORDS + 1):
        # Grow only from a foothold that already qualifies, so this stays linear
        # in practice instead of quadratic on every passage.
        if " ".join(words[start : start + MIN_MATCHED_WORDS]) not in haystack:
            continue
        end = start + MIN_MATCHED_WORDS
        while end < len(words) and " ".join(words[start : end + 1]) in haystack:
            end += 1
        longest = max(longest, end - start)
    return longest
