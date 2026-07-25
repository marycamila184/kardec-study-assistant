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

# Single source of truth for the five canonical book names, accent-tolerant
# and ordered so the longest names match first. `_BOOK_PATTERNS` (extraction)
# and `_BOOK_ALTERNATION` (the citation-shape predicate) are both derived from
# this list so the names cannot drift apart between the two.
_BOOK_REGEXES: list[tuple[str, str]] = [
    (r"Evangelho(?:\s+Segundo\s+o\s+Espiritismo)?", "ESE"),
    (r"Livro\s+dos\s+Esp[íi]ritos", "LE"),
    (r"Livro\s+dos\s+M[ée]diuns", "LM"),
    (r"C[ée]u\s+e\s+o\s+Inferno", "CI"),
    (r"G[êe]nese", "GE"),
]

_BOOK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), sigla) for pattern, sigla in _BOOK_REGEXES
]

# "LE-625", "LE 625", "LE625"
_SIGLA_REF = re.compile(r"\b(LE|LM|ESE|CI|GE)[-\s]?(\d{1,4})\b")

# "questão 625 do Livro dos Espíritos" / "questões 887-889 do Livro dos
# Espíritos" / "item 12 da Gênese" — matches the anchor (number, or number
# range, plus optional preposition); the book name is looked up in the
# following window via `_prose_window`, which stops at a real sentence
# boundary rather than at every period (see below).
_PROSE_ANCHOR = re.compile(
    r"(?:quest(?:[ãa]o|[õo]es)|itens|item|n[ºo°]?)\s*"
    r"(\d{1,4}(?:\s*[-–—]\s*\d{1,4})?)\s*(?:d[oaen]s?\s+)?",
    re.IGNORECASE,
)


def _expand_locator_number(raw: str) -> list[int]:
    """ "625" -> [625]; "887-889" (hyphen or en/em dash) -> [887, 888, 889]."""
    parts = re.split(r"\s*[-–—]\s*", raw)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        start, end = int(parts[0]), int(parts[1])
        if start <= end:
            return list(range(start, end + 1))
    return [int(parts[0])]


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

# --- the one unifying predicate ---------------------------------------------
#
# A fragment (parenthetical contents, or the text after "Fonte:") is a
# citation when, once one of the five canonical book names and any locator
# tokens are removed — in whatever order the model happened to write them,
# "book then locator" or "locator then book" — nothing but connective
# filler (articles, the "do/da" that glues a locator to a book name, and
# punctuation) is left. If any other word survives, the fragment is prose —
# it merely *mentions* a work — and must be left alone. This single shape is
# used for both the "Fonte:" line and parenthetical checks; there is no
# second, looser test for either, and it is order-agnostic by construction
# (it removes tokens rather than matching a fixed sequence).
#
# Locators covered: questão/questões (accent-tolerant), item/itens,
# capítulo/cap./cap, parte, nº/n°/no/n., arabic numbers and ranges
# ("887-889", hyphen or en/em dash), and roman numerals (II, IV, XIV).
_LOCATOR_WORD = (
    r"quest(?:[ãa]o|[õo]es)"  # questão, questao, questões, questoes
    r"|itens|item"
    r"|cap[íi]tulos?|cap\.?"
    r"|parte"
    r"|n[º°o]\.?"
)
_LOCATOR_NUMBER = r"\d{1,4}(?:\s*[-–—]\s*\d{1,4})?"
_LOCATOR_ROMAN = r"[IVXLCDM]+"

_BOOK_ALTERNATION = "|".join(pattern for pattern, _ in _BOOK_REGEXES)

# Connective filler: locator tokens, the article ("o"/"a"/"os"/"as") that can
# precede a book name or a locator, and the "do"/"da"/"dos"/"das" that glues
# a locator to a following book name ("questão 625 **do** Livro dos
# Espíritos"). Anything left over after removing the book name and all of
# this filler is meaningful prose, not a citation.
_FILLER_TOKEN = re.compile(
    rf"\b(?:{_LOCATOR_WORD}|{_LOCATOR_NUMBER}|{_LOCATOR_ROMAN}|d[oa]s?|[oa]s?)\b",
    re.IGNORECASE,
)

# Punctuation/whitespace left behind once tokens are removed.
_CONNECTIVE_PUNCT = re.compile(r"[\s,;:.\-–—]+")


def _is_citation_fragment(text: str) -> bool:
    """True when `text` is *only* a book name plus optional locators, in any
    order — the one predicate shared by both stripping paths. A book name is
    required: locator-shaped words with no book attribution (e.g. "questão
    42, item 3") are not a citation."""
    book_match = re.search(_BOOK_ALTERNATION, text, re.IGNORECASE)
    if not book_match:
        return False
    remainder = text[: book_match.start()] + text[book_match.end() :]
    remainder = _FILLER_TOKEN.sub("", remainder)
    remainder = _CONNECTIVE_PUNCT.sub("", remainder)
    return remainder == ""


# The model's own trailing source line, observed in the smoke test:
#   "📖 Fonte: O Livro dos Espíritos, questões 887-889."
# Anchored to a line start so a sentence containing "fonte:" is untouched.
# The content after the colon is what gets tested against the shared
# citation-shape predicate.
_SOURCE_LINE = re.compile(
    r"^(?P<full>[ \t]*(?:📖|\*|-)?[ \t]*Fontes?\s*:\s*(?P<content>.*))$",
    re.MULTILINE | re.IGNORECASE,
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
            for n in _expand_locator_number(m.group(1)):
                found.add(f"{sigla}-{n}")
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
    text = _SOURCE_LINE.sub(
        lambda m: "" if _is_citation_fragment(m.group("content")) else m.group("full"),
        text,
    )
    text = _PAREN_REF.sub(
        lambda m: "" if _is_citation_fragment(m.group(1)) else m.group(0), text
    )
    text = _SIGLA_REF.sub("", text)
    # Tidy the punctuation the removals leave behind.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()
