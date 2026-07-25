"""Model-written citation handling (source spec §6, §9.8).

Displayed citations always come from chunk metadata — this module never feeds
the UI. It exists to (a) remove citations the fine-tune writes unprompted, since
they duplicate and may contradict the real source chips, and (b) measure how
often those citations point outside what retrieval actually returned.

Blind spot, by construction: this only inspects citations the model *writes*.
Ungrounded prose carrying no citation at all is invisible here — that is what
`groundedness.py` measures.
"""

import re

SIGLAS: dict[str, str] = {
    "O Livro dos Espíritos": "LE",
    "O Livro dos Médiuns": "LM",
    "O Evangelho Segundo o Espiritismo": "ESE",
    "O Céu e o Inferno": "CI",
    "A Gênese": "GE",
}

# Accent-tolerant book patterns, ordered so the longest names match first.
_BOOK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Evangelho(?:\s+Segundo\s+o\s+Espiritismo)?", re.IGNORECASE), "ESE"),
    (re.compile(r"Livro\s+dos\s+Esp[íi]ritos", re.IGNORECASE), "LE"),
    (re.compile(r"Livro\s+dos\s+M[ée]diuns", re.IGNORECASE), "LM"),
    (re.compile(r"C[ée]u\s+e\s+o\s+Inferno", re.IGNORECASE), "CI"),
    (re.compile(r"G[êe]nese", re.IGNORECASE), "GE"),
]

# "LE-625", "LE 625", "LE625"
_SIGLA_REF = re.compile(r"\b(LE|LM|ESE|CI|GE)[-\s]?(\d{1,4})\b")

# "questão 625 do Livro dos Espíritos" / "item 12 da Gênese" — matches the
# anchor (number + optional preposition); the book name is looked up in the
# following window via `_prose_window`, which stops at a real sentence
# boundary rather than at every period (see below).
_PROSE_ANCHOR = re.compile(
    r"(?:quest[ãa]o|item|n[ºo°]?)\s*(\d{1,4})\s*(?:d[oaen]s?\s+)?",
    re.IGNORECASE,
)

# Common Portuguese abbreviations that end in a period without ending a
# sentence — e.g. "cap." in "questão 625 cap. II do Livro dos Espíritos".
_ABBREVIATIONS = {"cap", "art", "p", "ed", "v", "trad", "org", "vol", "sec"}

# Uppercase letters (plain and accented) that plausibly start a new sentence.
_UPPER_START = re.compile(r"[A-ZÀ-Ý]")


def _prose_window(text: str, start: int, limit: int = 100) -> str:
    """Text following a prose reference anchor, cut at the first period that
    actually ends a sentence — whitespace followed by an uppercase letter, or
    end of string/line — rather than at every period. A period that closes a
    known abbreviation ("cap.") or is followed by a lowercase word/roman
    numeral does not count as a boundary."""
    end = min(len(text), start + limit)
    window = text[start:end]
    i = 0
    while i < len(window):
        ch = window[i]
        if ch == "\n":
            return window[:i]
        if ch == ".":
            j = i
            while j > 0 and window[j - 1].isalpha():
                j -= 1
            word = window[j:i].lower()
            k = i + 1
            while k < len(window) and window[k] in " \t":
                k += 1
            at_end = k >= len(window)
            next_is_upper = k < len(window) and bool(_UPPER_START.match(window[k]))
            if word not in _ABBREVIATIONS and (at_end or next_is_upper):
                return window[:i]
        i += 1
    return window


# A parenthetical whose contents name one of the works.
_PAREN_REF = re.compile(r"\s*\(([^)]*)\)")

# A parenthetical counts as a citation only when it is essentially *just* a
# reference: an optional article, one of the five works, and then nothing
# but locators (numbers, questão/item/capítulo/cap./parte, punctuation). A
# parenthetical that names a work but continues as a full clause (other
# words) is prose, not a citation, and is left alone.
_PAREN_CITATION_SHAPE = re.compile(
    r"^\s*(?:[oa]s?\s+)?"
    r"(?:Evangelho(?:\s+Segundo\s+o\s+Espiritismo)?"
    r"|Livro\s+dos\s+Esp[íi]ritos"
    r"|Livro\s+dos\s+M[ée]diuns"
    r"|C[ée]u\s+e\s+o\s+Inferno"
    r"|G[êe]nese)"
    r"(?:[\s,;:\-–—]+(?:quest[ãa]o|item|cap[íi]tulo|cap\.|parte|\d+))*"
    r"[\s,;:\-–—.]*$",
    re.IGNORECASE,
)


def _paren_is_citation(text: str) -> bool:
    return bool(_PAREN_CITATION_SHAPE.match(text))


# The model's own trailing source line, observed in the smoke test:
#   "📖 Fonte: O Livro dos Espíritos, questões 887-889."
# Anchored to a line start so a sentence containing "fonte:" is untouched.
_SOURCE_LINE = re.compile(
    r"^[ \t]*(?:📖|\*|-)?[ \t]*Fontes?\s*:.*$", re.MULTILINE | re.IGNORECASE
)


def _sigla_in(text: str) -> str | None:
    for pattern, sigla in _BOOK_PATTERNS:
        if pattern.search(text):
            return sigla
    return None


def extract_model_citations(text: str) -> set[str]:
    """Citation ids the model wrote, normalized to `SIGLA-N`."""
    found = {f"{m.group(1)}-{int(m.group(2))}" for m in _SIGLA_REF.finditer(text)}
    for m in _PROSE_ANCHOR.finditer(text):
        window = _prose_window(text, m.end())
        sigla = _sigla_in(window)
        if sigla:
            found.add(f"{sigla}-{int(m.group(1))}")
    return found


def retrieved_ids(chunks: list[dict]) -> set[str]:
    """Citation ids for the chunks retrieval actually returned. Placeholder
    item numbers ("section-3") are not citable and are skipped."""
    ids = set()
    for c in chunks:
        m = c["metadata"]
        sigla = SIGLAS.get(m.get("book", ""))
        item = str(m.get("item_number", ""))
        if sigla and item.isdigit():
            ids.add(f"{sigla}-{int(item)}")
    return ids


def validate_model_citations(cited: set[str], retrieved: set[str]) -> dict:
    """Source spec §6 Regra 2. A citation outside the retrieved set means the
    model pulled from parametric memory rather than context."""
    invalidas = cited - retrieved
    return {
        "exibir": sorted(cited & retrieved),
        "alucinadas": sorted(invalidas),
        "confiavel": not invalidas,
    }


def strip_model_citations(text: str) -> str:
    """Removes model-written references so they never compete with the real
    source chips. The model's own "Fonte:" line is dropped whole (it carries
    invented question numbers); parentheticals naming a work are dropped whole;
    bare sigla refs are dropped in place."""
    text = _SOURCE_LINE.sub(lambda m: "" if _sigla_in(m.group(0)) else m.group(0), text)
    text = _PAREN_REF.sub(
        lambda m: "" if _paren_is_citation(m.group(1)) else m.group(0), text
    )
    text = _SIGLA_REF.sub("", text)
    # Tidy the punctuation the removals leave behind.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()
