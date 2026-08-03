import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;])\s+")
_WORD_BEFORE = re.compile(r"(\S+)\Z")
_OPENING_PUNCT = "([«\"“'"

# Tokens whose period abbreviates rather than closes a sentence. Measured over
# the five works (2026-08-02) by counting what precedes every candidate
# boundary, not assembled from intuition: `cap.` 442, `vv.` 291, `pág.` 95,
# `Art.` 30, plus the long tail below. `etc.` is deliberately absent — it ends
# a sentence about as often as not, and a wrong split there costs far less than
# never splitting a list that runs on.
_ABBREVIATIONS = frozenset(
    {
        "cap",
        "vv",
        "pag",
        "pág",
        "art",
        "no",
        "nº",
        "n°",
        "sr",
        "sra",
        "dr",
        "dra",
        "st",
        "sta",
        "sec",
        "séc",
        "ed",
        "fig",
        "vol",
    }
)


def _closes_a_sentence(paragraph: str, end: int) -> bool:
    """Whether the punctuation ending at `end` really ends a sentence.

    Only periods are ambiguous — `!`, `?` and `;` are not used as abbreviation
    marks here. A period does NOT end a sentence when it closes:

    * a single letter — `S.` for São, the personal initials in `A. Kardec`,
      and above all the `P.`/`R.` (Pergunta/Resposta) markers that open every
      line of the O Céu e o Inferno evocations, where cutting after the marker
      leaves it stranded from the answer it introduces;
    * one of the measured citation abbreviations in `_ABBREVIATIONS`.

    Numbers are NOT excluded: `1857.` genuinely ends sentences, and the item
    markers (`8.`) sit at the start of a paragraph, which the paragraph pass
    has already separated — so excluding them would suppress 3009 real
    boundaries to fix none.
    """
    match = _WORD_BEFORE.search(paragraph, 0, end)
    if not match:
        return True
    word = match.group(1)
    if not word.endswith("."):
        return True
    core = word[:-1].lstrip(_OPENING_PUNCT)
    if len(core) == 1 and core.isalpha():
        return False
    return core.lower() not in _ABBREVIATIONS


def _split_sentences(paragraph: str) -> list[str]:
    """The paragraph's sentences, ignoring boundaries that are abbreviations.

    Suppressing a boundary is safe by construction: the caller falls back to
    word splitting for anything still over max_chars, so a run without a real
    sentence end is cut anyway — just not in a place that strands a citation.
    """
    sentences = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(paragraph):
        if _closes_a_sentence(paragraph, match.start()):
            sentences.append(paragraph[start : match.start()])
            start = match.end()
    sentences.append(paragraph[start:])
    return [s for s in sentences if s]


def _split_oversized_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """
    Splits a single paragraph that already exceeds max_chars, preferring
    sentence boundaries and falling back to word boundaries.
    """
    pieces = []
    buffer = ""

    for sentence in _split_sentences(paragraph):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if buffer:
                pieces.append(buffer.strip())
                buffer = ""
            word_buffer = ""
            for word in sentence.split(" "):
                candidate = f"{word_buffer} {word}".strip()
                if word_buffer and len(candidate) > max_chars:
                    pieces.append(word_buffer.strip())
                    word_buffer = word
                else:
                    word_buffer = candidate
            if word_buffer:
                pieces.append(word_buffer.strip())
        else:
            candidate = f"{buffer} {sentence}".strip()
            if buffer and len(candidate) > max_chars:
                pieces.append(buffer.strip())
                buffer = sentence
            else:
                buffer = candidate

    if buffer:
        pieces.append(buffer.strip())

    return pieces


def split_with_paragraph_breaks(
    text: str, max_chars: int = 800
) -> list[tuple[str, bool]]:
    """
    Splits long text into subchunks of at most max_chars, preserving
    paragraph structure and, for paragraphs too long on their own,
    sentence/word structure.

    Returns (subchunk, starts_paragraph) pairs. `starts_paragraph` is False
    only for the pieces of a paragraph that had to be cut mid-way to fit
    max_chars — it is what tells reassembly whether the cut was a real
    paragraph break in the source or an artifact of the size limit. 28% of the
    corpus's interior boundaries are mid-paragraph (measured 2026-08-02), so
    guessing this from the text is not an option; see `join_subchunks`.
    """
    paragraphs = text.split("\n")
    subchunks: list[tuple[str, bool]] = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if buffer.strip():
                subchunks.append((buffer.strip(), True))
            buffer = ""
            for index, piece in enumerate(
                _split_oversized_paragraph(paragraph, max_chars)
            ):
                subchunks.append((piece, index == 0))
        elif len(buffer) + len(paragraph) < max_chars:
            buffer += paragraph + "\n"
        else:
            if buffer.strip():
                subchunks.append((buffer.strip(), True))
            buffer = paragraph + "\n"

    if buffer.strip():
        subchunks.append((buffer.strip(), True))

    return subchunks


def split_into_subchunks(text: str, max_chars: int = 800) -> list[str]:
    """The subchunk texts alone, for callers that do not reassemble."""
    return [piece for piece, _ in split_with_paragraph_breaks(text, max_chars)]


def join_subchunks(pieces) -> str:
    """The inverse of `split_with_paragraph_breaks`: puts an item back together
    as the source had it.

    Lives next to the splitter so the two cannot drift. The separator is not a
    style choice — "Da Obra" renders the result with `white-space: pre-wrap`,
    so every newline invented here is a line the reader sees. A paragraph cut
    only because it was over max_chars rejoins with the single space the split
    consumed; a real paragraph break rejoins with the single "\\n" the parser
    stored (it drops blank lines, so "\\n" is the only paragraph separator
    inside a chunk).

    Accepts (text, starts_paragraph) pairs.
    """
    out = ""
    for index, (text, starts_paragraph) in enumerate(pieces):
        if index:
            out += "\n" if starts_paragraph else " "
        out += text
    return out
