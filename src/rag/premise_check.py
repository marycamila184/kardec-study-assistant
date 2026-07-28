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

**It corrects the premise; it does not withhold the answer.** Measured against
the 44 curated study questions in data/paths/ — hand-reviewed labels nobody
wrote with this check in mind — it flagged none of them, and caught 7 of 10
out-of-doctrine questions. Zero false positives is what makes acting on it
defensible; correcting rather than refusing is what keeps a wrong flag cheap.

The note is also the answer the reader needed. Someone asking how something
affects their ectoplasma is, underneath, asking whether that is doctrine — and
"the works do not use this term" answers that directly, in a way that refusing
the turn never would.

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
    # Words a reader uses to ASK, which 19th-century doctrine prose has no
    # reason to contain. "exlique" reached production as a flagged premise
    # because "explique" is not in the works either, so the typo check had
    # nothing to match it against. These are about the request, never about
    # doctrine, so they can never be a premise worth correcting.
    "explique",
    "explica",
    "explicar",
    "explicacao",
    "mostre",
    "mostrar",
    "conte",
    "contar",
    "cite",
    "citar",
    "citacao",
    "citacoes",
    "referencia",
    "referencias",
    "resuma",
    "resumo",
    "detalhe",
    "detalhes",
    "melhor",
    "preciso",
    "queria",
    "quero",
    "gostaria",
    "entendi",
    "obrigada",
    "obrigado",
    "ajuda",
    "ajudar",
    "sabe",
    "saber",
    "conhece",
    "outras",
    "exemplo",
    "exemplos",
    "sobre",
    "trecho",
    "trechos",
    "texto",
    "textos",
    "parte",
    "partes",
    "coisa",
    "coisas",
    "assunto",
    "tema",
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
_words_by_prefix: dict[str, set[str]] | None = None

# A typo sits one or two edits from a real word; a foreign concept sits far from
# everything. "exlique" is one edit from "explique"; "ectoplasma" is nowhere
# near anything Kardec wrote.
#
# This exists because the check went to production and told a reader "as obras
# não usam o termo *exlique*". The 44 curated study-path labels that justified
# shipping it were hand-reviewed prose — nobody misspells anything in those, and
# real people misspell constantly.
_MAX_TYPO_DISTANCE = 1


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


def _build_index(vocabulary: str) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    # The stopwords go in alongside the corpus. They are the words a reader
    # uses to ASK, which the works have no reason to contain — so a typo of
    # one has nothing in Kardec to be matched against. "exlique" is one edit
    # from "explique" and zero edits from nothing at all, which is exactly
    # how it reached production as a flagged premise.
    for word in set(_WORD.findall(vocabulary)) | _STOPWORDS:
        if len(word) >= 2:
            index.setdefault(word[:2], set()).add(word)
    return index


def _prefix_index() -> dict[str, set[str]]:
    """Corpus words grouped by their first two letters.

    Edit distance against every word in five books, per term, per request would
    be absurd. A typo almost always keeps its opening — "exlique"/"explique",
    "espeiritos"/"espiritos" — so comparing only against words that start the
    same way is both far cheaper and about as accurate.
    """
    global _words_by_prefix
    if _words_by_prefix is None:
        _words_by_prefix = _build_index(corpus_vocabulary())
    return _words_by_prefix


def _within(a: str, b: str, limit: int) -> bool:
    """Levenshtein, abandoned as soon as it cannot come in under `limit`."""
    if abs(len(a) - len(b)) > limit:
        return False
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                previous[j - 1]
                if ca == cb
                else 1 + min(previous[j - 1], previous[j], current[j - 1])
            )
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit


def looks_like_a_typo(term: str, index: dict[str, set[str]] | None = None) -> bool:
    """Whether some word in the works is a plausible correction of `term`.

    One edit, not two. Two was tried and it swallowed real findings: "chakras"
    is two edits from "chamas" and "energéticos" two from "energéticas", so the
    check stopped catching the very terms it exists for. One edit still catches
    what people actually mistype — "exlique" for "explique", "espeiritos" for
    "espíritos" — because a slip is usually a single key.
    """
    index = _prefix_index() if index is None else index
    return any(
        _within(term, candidate, _MAX_TYPO_DISTANCE)
        for candidate in index.get(term[:2], ())
    )


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

    # The typo index is built from the SAME vocabulary, so an injected one is
    # honoured end to end. They used to disagree: the caller could pass a
    # stand-in corpus and still be measured against the real books.
    if vocabulary is None:
        vocabulary, index = corpus_vocabulary(), _prefix_index()
    else:
        index = _build_index(vocabulary)
    if not vocabulary:
        return []
    return [
        t
        for t in _terms(question)
        if t[:6] not in vocabulary and not looks_like_a_typo(t, index)
    ]


def premise_note(terms: list[str]) -> str:
    """The deterministic correction, written in code and never left to the model.

    Added before the answer rather than after: the reader has to meet the
    correction before the explanation, or the explanation reads as confirmation
    of a premise the works do not support.
    """
    if not terms:
        return ""
    if len(terms) == 1:
        subject = f"o termo *{terms[0]}*"
    else:
        listed = ", ".join(f"*{t}*" for t in terms[:-1])
        subject = f"os termos {listed} e *{terms[-1]}*"
    return (
        f"As obras de Allan Kardec não usam {subject}. O que segue vem das "
        "passagens que tratam de assuntos próximos — não do conceito como você "
        "o nomeou.\n\n"
    )
