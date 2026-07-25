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

# "questão 625 do Livro dos Espíritos" / "item 12 da Gênese" — number first,
# book within the next ~60 chars. The lookahead is restricted to `[^.\n]` so
# it cannot cross a sentence boundary (or newline) into an unrelated clause.
_PROSE_REF = re.compile(
    r"(?:quest[ãa]o|item|n[ºo°]?)\s*(\d{1,4})\s*(?:d[oaen]s?\s+)?([^.\n]{0,60})",
    re.IGNORECASE,
)

# A parenthetical whose contents name one of the works.
_PAREN_REF = re.compile(r"\s*\(([^)]*)\)")

# Citation shape inside a parenthetical/source line: a number, or a word that
# only makes sense as a locator (questão/item/capítulo/cap./parte). Without
# this, any parenthetical or "Fonte:" line that merely mentions a work's name
# in passing prose would be mistaken for a citation.
_CITATION_SHAPE = re.compile(
    r"\d|quest[ãa]o|item|cap[íi]tulo|cap\.|parte", re.IGNORECASE
)


def _looks_like_citation(text: str) -> bool:
    return bool(_sigla_in(text) and _CITATION_SHAPE.search(text))


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
    for m in _PROSE_REF.finditer(text):
        sigla = _sigla_in(m.group(2))
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
    text = _SOURCE_LINE.sub(
        lambda m: "" if _looks_like_citation(m.group(0)) else m.group(0), text
    )
    text = _PAREN_REF.sub(
        lambda m: "" if _looks_like_citation(m.group(1)) else m.group(0), text
    )
    text = _SIGLA_REF.sub("", text)
    # Tidy the punctuation the removals leave behind.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()
