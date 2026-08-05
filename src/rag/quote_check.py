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

from src.rag.retriever import prompt_text

# Below this, a "quotation" is usually a term in scare quotes ("campo de
# energia", "provação") rather than a claim about what the text says. Checking
# those would flag ordinary prose constantly.
MIN_QUOTED_WORDS = 6

# The second way a quotation can be supported, added 2026-08-04 and measured
# before it was added. The anchor above is binary, and that cost correct
# answers in production: asked for Q.1009, the model wrote
#
#     "a duração das penas depende dos esforços do culpado"
#
# where the work says "…dependa dos esforços do culpado" — one verb moved from
# the subjunctive to the indicative to fit the model's own sentence. Nine
# words, four possible 6-word windows, the altered word inside all four. So
# nothing anchored and the reader was told the works do not address the
# question, printed underneath the passage that answers it.
#
# Bigram coverage is the fraction of the quotation's adjacent word pairs found
# in the haystack. It measures how much of the sentence is the source's, which
# is a different question from the longest intact fragment: a paraphrase can
# carry a five-word fragment and still be mostly the model's words. Measured
# over 70 production turns (scripts/measure_quote_guard.py, results in
# logs/quote-guard-calibration.txt):
#
#     quotations accepted in production   n=42   0.87 – 1.00
#     re-inflected quotations, withheld   n= 4   0.67 – 0.75
#     paraphrase-as-quotation, withheld   n= 3   0.14 – 0.33
#     inventions (control)                n= 4   0.00 – 0.26
#
# The cut sits in the 0.33–0.67 gap. **The band is what the test guards, not
# the number** — the same rule `max_distance` follows. Anything above 0.33 and
# below 0.67 preserves every decision measured here; move outside it and
# re-measure.
#
# This only ever ADDS support: a quotation that anchors is supported as before,
# so nothing that passed the old check fails the new one.
MIN_BIGRAM_COVERAGE = 0.5

# Straight, curly, and the guillemets the Portuguese editions use.
#
# Newlines are excluded from the span, and it is not cosmetic. Pairing any two
# quote characters lets the closing quote of one term pair with the opening
# quote of the next and swallow the prose between them — in the 2026-07-28
# probe that captured the model's own honest sentence about chakras, spanning a
# paragraph break, and withheld a correct answer over it. A real quotation from
# these works does not cross a blank line.
# No minimum length. There used to be one, and it broke the pairing: a short
# quoted term like "glândula pineal" fell below it, so its closing quote paired
# with the NEXT term's opening quote and swallowed the prose between them —
# withholding a correct answer. Every quoted span is matched so the alternation
# stays right; MIN_QUOTED_WORDS then decides which spans are worth checking.
_QUOTED = re.compile(
    r"[\"“”«]([^\"“”«»\n]{1,600})[\"“”»]",
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


def _haystack(chunks: list[dict]) -> str:
    """Everything that went to the prompt, normalised.

    Reads `prompt_text` and not `content`, because that is what the model was
    shown: with expansion on, a chunk's `content` is only the subchunk that won
    retrieval while the model read the item around it. Checking the narrower
    text would flag a quotation the model took **correctly** from a neighbouring
    subchunk as fabricated — and a hit here discards the whole answer.

    /study reached the same rule from the other side on 2026-07-28: explicador
    passes `available` (chunks + commentary + related), not `ctx["chunks"]`. The
    invariant is that the haystack is everything the model could quote from.
    """
    return " ".join(_normalise(prompt_text(c)) for c in chunks)


def _bigrams(normalised: str) -> set[str]:
    words = normalised.split()
    return {f"{a} {b}" for a, b in zip(words, words[1:])}


def coverage(words: list[str], haystack_bigrams: set[str]) -> float:
    """Fraction of the quotation's adjacent word pairs present in the corpus.

    A changed word costs the two bigrams that touch it, wherever it sits. The
    longest-run alternative is hostage to position — change the middle word of
    a nine-word quotation and the run halves, change the last and it barely
    moves — which is why it cannot tell a re-inflection from a paraphrase.
    """
    if len(words) < 2:
        return 0.0
    pairs = [f"{a} {b}" for a, b in zip(words, words[1:])]
    return sum(p in haystack_bigrams for p in pairs) / len(pairs)


def _is_supported(words: list[str], haystack: str, haystack_bigrams: set[str]) -> bool:
    """Whether the corpus backs this quotation, by either route.

    The anchor first, because it is the cheap exact case and because keeping it
    means no quotation that used to pass can start failing.
    """
    if _has_anchor(words, haystack):
        return True
    return coverage(words, haystack_bigrams) >= MIN_BIGRAM_COVERAGE


def find_unsupported_quotes(answer: str, chunks: list[dict]) -> list[str]:
    """The quotations in `answer` that appear in no retrieved chunk.

    Returns them in the order written, as the model wrote them, so a log entry
    can be read without cross-referencing anything.
    """
    if not answer:
        return []

    haystack = _haystack(chunks)
    haystack_bigrams = _bigrams(haystack)
    unsupported = []

    for match in _QUOTED.finditer(answer):
        quoted = match.group(1)
        words = _words(quoted)
        if len(words) < MIN_QUOTED_WORDS:
            continue
        if not _is_supported(words, haystack, haystack_bigrams):
            unsupported.append(quoted.strip())

    return unsupported


def _has_anchor(words: list[str], haystack: str) -> bool:
    """Whether any run of MIN_QUOTED_WORDS consecutive words is in the corpus.

    Requiring the WHOLE quotation to be verbatim conflated two different things,
    and the 2026-07-28 probe showed it costing a good answer at a rate no
    reader would tolerate. The model opens a quotation, quotes Kardec correctly,
    then carries on paraphrasing inside the same quotation marks:

        "se emprega para exprimir coisas muito diferentes. Em uma acepção,
         a alma se refere ao princípio da vida, uma"

    The first half is real; the rest is the model's own words. That is a sloppy
    quotation boundary — worth fixing in the prompt, not worth withholding an
    otherwise correct answer over.

    Fabrication is the case where NO part of the quotation is in the corpus at
    all: nothing was being quoted, and the quotation marks are decoration on an
    invention. That is what this returns False for, and only that.
    """
    for i in range(len(words) - MIN_QUOTED_WORDS + 1):
        if " ".join(words[i : i + MIN_QUOTED_WORDS]) in haystack:
            return True
    return False


class StreamingQuoteGuard:
    """Holds quoted text back until it can be checked against the corpus.

    Found in production on 2026-07-28: the guard ran at the end of generation,
    so a fabricated quotation streamed onto the screen in full and was only
    replaced when `done` arrived. The reader watched invented doctrine being
    written and then saw it vanish. A guard whose whole purpose is that
    fabricated doctrine is never shown was showing it and taking it back.

    So the check moves into the stream. Prose flows normally; the moment a
    quotation opens, everything from the opening mark is held. When it closes,
    the span is verified: supported, it is released whole; unsupported, the
    caller is told to abandon the answer before a word of it was seen.

    The cost is that quoted text arrives in one piece rather than word by word.
    That is the right trade: a quotation is the part a reader is most likely to
    copy, and it is the part that must not be wrong.
    """

    _OPENING = '"“«'
    _CLOSING = '"”»'

    def __init__(self, chunks: list[dict]) -> None:
        self._haystack = _haystack(chunks)
        self._bigrams = _bigrams(self._haystack)
        self._held = ""
        self.violated = False
        self.offending: str | None = None

    def feed(self, chunk: str) -> str:
        """Returns the text safe to show now. Check `violated` after each call:
        once it is set nothing further may be emitted."""
        out = []
        for char in chunk:
            if self._held:
                self._held += char
                if char in self._CLOSING and len(self._held) > 1:
                    released = self._close()
                    if self.violated:
                        return "".join(out)
                    out.append(released)
                continue
            if char in self._OPENING:
                self._held = char
                continue
            out.append(char)
        return "".join(out)

    def _close(self) -> str:
        span = self._held
        self._held = ""
        inner = span[1:-1]
        words = _words(inner)
        # Same predicate as the non-streaming lane, deliberately: a streamed
        # answer must end up identical to what POST /chat returns, and two
        # copies of a support test are two tests that can drift apart.
        if len(words) >= MIN_QUOTED_WORDS and not _is_supported(
            words, self._haystack, self._bigrams
        ):
            self.violated = True
            self.offending = inner.strip()
            return ""
        return span

    def flush(self) -> str:
        """A quotation that never closed was prose after all — withholding it
        would silently truncate the answer."""
        held, self._held = self._held, ""
        return held
