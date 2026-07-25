"""Post-hoc checks for rules that are enforced only by prompt today.

An 8B fine-tune holds prompt constraints less reliably than a 70B, so the
mechanical rules get a code-level backstop. The non-mechanical ones deliberately
do not: reflect's no-advice constraint cannot be detected reliably, and a check
that half-works is worse than none.
"""

import re

# A closing question: the final sentence ends in "?" with no prose after it.
_TRAILING_QUESTION = re.compile(r"(?:(?<=[.!?])|(?<=\n))\s*[^.!?\n]{1,300}\?\s*$")

# "o Espiritismo" as the subject of a verb — the personification CLAUDE.md bans.
_PERSONIFICATION = re.compile(
    r"\bo\s+Espiritismo\s+(?!é\b|foi\b)[a-zà-ú]+(?:a|e|ou|em|iu|am|z)\b",
    re.IGNORECASE,
)


def strip_trailing_question(text: str) -> str:
    """Removes a closing question. /chat answers must never end with one —
    follow-ups belong in [SEGUIR]. Never strips the text to empty: a
    single-sentence answer is returned unchanged."""
    stripped = _TRAILING_QUESTION.sub("", text).strip()
    return stripped if stripped else text


def counts_personification(text: str) -> int:
    """Occurrences of "o Espiritismo" acting as an agent. Log-only: doctrine
    prose is never rewritten automatically."""
    return len(_PERSONIFICATION.findall(text))
