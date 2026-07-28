"""Terms a question introduces that the retrieved passages never use.

Found in production on 2026-07-28, and it is the failure the quotation guard
cannot see. Asked "o que Kardec fala sobre a aura", the model correctly answered
that it found nothing. Asked "isso influencia o meu ectoplasma e a minha aura",
it explained both at length as doctrine — same absent concept, but embedded in
the question as an established fact rather than put up for checking.

The invention was in plain prose with nothing quoted, so nothing caught it. What
IS checkable is the premise: "ectoplasma" appears in no retrieved passage, and
an answer that explains it anyway is explaining something the works do not
contain.

**Measurement only, for now.** A gate here would decide whether a reader gets an
answer at all, and this project has twice shipped a guard tuned by reasoning
instead of by evidence — both times it withheld correct answers. So this counts
and logs, the numbers get looked at, and only then does anyone decide what it
should do.

See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md
"""

import logging
import pathlib
import re
import unicodedata

# Words too common to carry a premise. Deliberately short: the point is to catch
# a NOUN the works never use, and over-filtering hides exactly that.
_STOPWORDS = {
    "sobre",
    "quando",
    "porque",
    "aquele",
    "aquela",
    "aquilo",
    "quanto",
    "muito",
    "pouco",
    "todos",
    "todas",
    "outro",
    "outra",
    "outros",
    "outras",
    "mesmo",
    "mesma",
    "ainda",
    "depois",
    "antes",
    "entre",
    "contra",
    "assim",
    "como",
    "onde",
    "qual",
    "quais",
    "esse",
    "essa",
    "isso",
    "este",
    "esta",
    "isto",
    "disso",
    "nisso",
    "desse",
    "dessa",
    "deste",
    "desta",
    "para",
    "pelo",
    "pela",
    "seus",
    "suas",
    "meu",
    "minha",
    "meus",
    "minhas",
    "voce",
    "voces",
    "kardec",
    "espiritismo",
    "espirita",
    "doutrina",
    "obras",
    "livro",
    "questao",
    "item",
    "capitulo",
    "trecho",
    "passagem",
    "fala",
    "falar",
    "diz",
    "dizer",
    "explica",
    "explicar",
    "significa",
    "acontece",
    "existe",
    "pode",
    "podem",
    "tem",
    "temos",
    "fazer",
    "sendo",
    "seria",
    "sobre",
    "algo",
    "alguma",
    "algum",
    "gente",
    "pessoa",
    "pessoas",
}

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[^\W\d_]{5,}", re.UNICODE)


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _terms(text: str) -> list[str]:
    """Content words worth checking: five letters or more, not stopwords.

    Five because Portuguese function words are mostly shorter, and a term that
    carries a doctrinal premise ("ectoplasma", "chakras", "reencarnacao") is
    almost never four letters.
    """
    seen: list[str] = []
    for word in _WORD.findall(_normalise(text)):
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
    return seen


_CORPUS_DIR = pathlib.Path("data/markdown_files")
_vocabulary: str | None = None


def corpus_vocabulary() -> str:
    """Every word in the five works, normalised, as one searchable blob.

    Loaded once and kept. The hand-reviewed markdown is the authoritative
    source, and it is a few megabytes — cheap next to being wrong about whether
    Kardec used a word.
    """
    global _vocabulary
    if _vocabulary is None:
        parts = []
        try:
            for path in sorted(_CORPUS_DIR.glob("*.md")):
                parts.append(_normalise(path.read_text(encoding="utf-8")))
        except OSError:
            logger.exception("corpus vocabulary unavailable; premise check off")
        _vocabulary = " ".join(parts)
    return _vocabulary


def unsupported_terms(
    question: str, chunks: list[dict], vocabulary: str | None = None
) -> list[str]:
    """Content words from the question that the WORKS never use.

    Measured against the whole corpus, not only the retrieved passages. The
    first version checked the passages alone and flagged "funciona" and "papel"
    — ordinary words that happen to be long, absent from those particular
    chunks and present throughout Kardec. Two false positives in ten legitimate
    questions, and both vanish here: what makes "ectoplasma" a premise is not
    that this retrieval missed it, but that the works never contain it.

    Substring matching on purpose: "perispirito" should match "perispiritico",
    and a stemmer would be a second thing to get wrong. The bias is toward
    finding a term present, because a false "this term is absent" is the
    expensive direction.

    `chunks` stays in the signature: with nothing retrieved the not-found path
    already handles the turn, and flagging every word there would be noise.
    """
    if not question or not chunks:
        return []

    vocabulary = corpus_vocabulary() if vocabulary is None else vocabulary
    if not vocabulary:
        return []
    return [t for t in _terms(question) if t[:6] not in vocabulary]
