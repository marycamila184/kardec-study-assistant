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


def counts_personification(text: str) -> int:
    """Occurrences of "o Espiritismo" acting as an agent. Log-only: doctrine
    prose is never rewritten automatically."""
    return len(_PERSONIFICATION.findall(text))


# System vocabulary that means nothing to a reader: they do not know a retrieval
# step exists. The prompt already forbids these by name, with an example — and
# on 2026-07-28 an answer said "as passagens recuperadas não contêm informações
# suficientes" anyway. A prose rule with no check in code is a suggestion.
#
# A CLOSED list is what makes this one mechanical, unlike "never personify o
# Espiritismo", which needs judgement. Substitution rather than withholding,
# because the answer is grounded and only the word is wrong — discarding a
# correct answer over vocabulary would repeat the mistake the quotation guard
# made before it was calibrated.
#
# The replacements are meaning-preserving on purpose: "as passagens recuperadas
# não contêm X" becomes "as obras não contêm X", which is what the sentence was
# already saying, now said to the person reading it.
_INTERNAL_TERMS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bas passagens recuperadas\b", re.IGNORECASE), "as obras"),
    (re.compile(r"\bdas passagens recuperadas\b", re.IGNORECASE), "das obras"),
    (re.compile(r"\bnas passagens recuperadas\b", re.IGNORECASE), "nas obras"),
    (re.compile(r"\bos trechos fornecidos\b", re.IGNORECASE), "as obras"),
    (re.compile(r"\bnos trechos fornecidos\b", re.IGNORECASE), "nas obras"),
    (re.compile(r"\bo material acima\b", re.IGNORECASE), "as obras"),
    (re.compile(r"\bo material fornecido\b", re.IGNORECASE), "as obras"),
    (re.compile(r"\bos textos fornecidos\b", re.IGNORECASE), "as obras"),
)


def strip_internal_terms(text: str) -> tuple[str, int]:
    """Replaces system vocabulary with what a reader can understand.

    Returns (text, substitutions) so the caller can log how often the prompt
    rule is being ignored — the number is the only way to know whether the rule
    is working, since the substitution hides the symptom.
    """
    count = 0
    for pattern, replacement in _INTERNAL_TERMS:
        text, made = pattern.subn(replacement, text)
        count += made
    return text, count
