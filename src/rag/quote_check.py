"""Quoted text attributed to the works must exist in the works.

Found in production on 2026-07-28. Asked about "duplo etéreo ou aura" — a
theosophical notion, not Kardec's vocabulary — the model did not say the works
are silent on it. It wrote a sentence, put it in quotation marks, attributed it
to Kardec and gave a chapter and an item:

    Kardec escreve que "o duplo etéreo é uma espécie de envoltório fluídico
    que envolve o corpo físico e é uma extensão do perispírito"
    (A Gênese, capítulo "OS FLUIDOS", item 18).

Nothing caught it. `citations.py` only recognises number-before-book references
("item 18 da Gênese"), so it did not even log the citation; and everything that
mutates the answer sits behind the prose lane, which production does not run.

This guard does not depend on citation format, on the model's cooperation, or
on any prompt. A quotation is a factual claim about what a text says, and the
retrieved passages are right there to check it against.

**Normalisation is deliberately generous.** The model reflows whitespace,
changes quote characters and occasionally fixes the archaic spelling of the
1860s editions ("freqüentemente"). None of that is fabrication, and flagging it
would train everyone to ignore the flag. Only a quotation whose words are not in
the retrieved text at all is a fabrication.

See docs/superpowers/specs/2026-07-28-quote-verification-design.md
"""

import re
import unicodedata

# Below this, a "quotation" is usually a term in scare quotes ("campo de
# energia", "provação") rather than a claim about what the text says. Checking
# those would flag ordinary prose constantly.
MIN_QUOTED_WORDS = 6

# Straight, curly, and the guillemets the Portuguese editions use.
_QUOTED = re.compile(
    r"[\"“”«]([^\"“”«»]{20,600})[\"“”»]",
)


def _normalise(text: str) -> str:
    """Casefold, strip accents, collapse whitespace and drop punctuation.

    Accents go because the works' spelling is not stable across editions and the
    model silently modernises it; punctuation goes because a quotation that
    changes a comma is still the same quotation.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Whitespace is collapsed AFTER punctuation becomes space, not before:
    # dropping a comma leaves two spaces, and a haystack spaced differently from
    # the needle fails to match text that is in fact identical.
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", stripped)).strip()


def _words(text: str) -> list[str]:
    return _normalise(text).split()


def find_unsupported_quotes(answer: str, chunks: list[dict]) -> list[str]:
    """The quotations in `answer` that appear in no retrieved chunk.

    Returns them in the order written, as the model wrote them, so a log entry
    can be read without cross-referencing anything.
    """
    if not answer:
        return []

    haystack = " ".join(_normalise(c.get("content", "")) for c in chunks)
    unsupported = []

    for match in _QUOTED.finditer(answer):
        quoted = match.group(1)
        words = _words(quoted)
        if len(words) < MIN_QUOTED_WORDS:
            continue
        if " ".join(words) not in haystack:
            unsupported.append(quoted.strip())

    return unsupported
