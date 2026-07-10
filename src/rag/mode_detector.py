import re
import unicodedata

# Accent-tolerant ([ãa]) because users often type without accents; must stay
# in sync with _ITEM_NUMBER_PATTERNS below, or the /chat direct lookup fires
# without the client button (mode undetected) or vice versa.
_STUDY_PATTERNS = [
    re.compile(r"\bquest[ãa]o\s+\d+", re.IGNORECASE),
    re.compile(r"\bitem\s+\d+", re.IGNORECASE),
    re.compile(r"\bq\.\s*\d+", re.IGNORECASE),
    re.compile(r"explique\s+a\s+quest[ãa]o", re.IGNORECASE),
    re.compile(r"o\s+que\s+(diz|fala)\s+.+\d+", re.IGNORECASE),
]

# Situational / emotional cues that suggest the Refletir flow rather than a
# dry factual answer. Kept intentionally soft — a false positive only surfaces
# an optional button, never changes the answer itself.
_SITUATIONAL_PATTERNS = [
    re.compile(r"\b(medo|receio|pavor)\b", re.IGNORECASE),
    re.compile(r"\b(luto|perdi|faleceu|morreu)\b", re.IGNORECASE),
    re.compile(r"\bansiedade\b|\bansios[oa]\b|\bang[uú]stia\b", re.IGNORECASE),
    re.compile(r"\b(sozinh[oa]|solid[ãa]o)\b", re.IGNORECASE),
    re.compile(
        r"\b(sofrimento|sofrendo|tristeza|triste|deprimid[oa])\b", re.IGNORECASE
    ),
    re.compile(r"\b(culpa|culpad[oa])\b", re.IGNORECASE),
    re.compile(r"\b(raiva|[óo]dio|rancor|m[áa]goa)\b", re.IGNORECASE),
    re.compile(r"\bdesespero\b|\bdesesperad[oa]\b", re.IGNORECASE),
    re.compile(r"n[ãa]o\s+sei\s+(o\s+que\s+fazer|como\s+lidar|lidar)", re.IGNORECASE),
    re.compile(r"\bpassando\s+por\b", re.IGNORECASE),
]


# Ordered: explicit forms ("questão 132", "item 45", "q. 76") tried before the
# loose "o que diz ... 200" fallback, so the most intentional phrasing wins.
# The is_questao flag marks the "questão N" / "Q. N" forms: by universal
# spiritist convention those refer to O Livro dos Espíritos (the only work
# whose numbered entries are called questões, numbered globally 1-1019), so
# they default the book to LE when none is named. "item N" stays generic.
_ITEM_NUMBER_PATTERNS = [
    (re.compile(r"\bquest[ãa]o\s+(?:n[ºo°.]?\s*)?(\d+)", re.IGNORECASE), True),
    (re.compile(r"\bitem\s+(?:n[ºo°.]?\s*)?(\d+)", re.IGNORECASE), False),
    (re.compile(r"\bq\.\s*(\d+)", re.IGNORECASE), True),
    (re.compile(r"o\s+que\s+(?:diz|fala)\s+.+?(\d+)", re.IGNORECASE), False),
]

_LIVRO_ESPIRITOS = "O Livro dos Espíritos"

# Maps user phrasings to the canonical book names used by /study
# (same canonical names as parsing_pipeline.BOOK_NAME_MAP values).
_BOOK_PATTERNS = [
    (re.compile(r"livro\s+dos\s+esp[íi]ritos", re.IGNORECASE), "O Livro dos Espíritos"),
    (re.compile(r"livro\s+dos\s+m[ée]diuns", re.IGNORECASE), "O Livro dos Médiuns"),
    (
        re.compile(r"evangelho", re.IGNORECASE),
        "O Evangelho Segundo o Espiritismo",
    ),
    (re.compile(r"c[ée]u\s+e\s+(?:o\s+)?inferno", re.IGNORECASE), "O Céu e o Inferno"),
    (re.compile(r"g[êe]nese", re.IGNORECASE), "A Gênese"),
]


def detect_suggested_mode(question: str) -> str | None:
    if any(p.search(question) for p in _STUDY_PATTERNS):
        return "estudar_obra"
    if any(p.search(question) for p in _SITUATIONAL_PATTERNS):
        return "refletir"
    return None


# Pure acknowledgment / closing words. A message is treated as small talk only
# when EVERY word is one of these (or a filler below) and it carries no question
# mark. Deliberately high-precision: a miss just falls back to a normal grounded
# answer, whereas a false positive would swallow a real question. Stored without
# accents; is_smalltalk strips accents before matching.
_ACK_TOKENS = frozenset(
    {
        "obrigado",
        "obrigada",
        "obg",
        "obgd",
        "vlw",
        "valeu",
        "entendi",
        "entendido",
        "entendida",
        "compreendi",
        "entendeu",
        "perfeito",
        "otimo",
        "certo",
        "ok",
        "okay",
        "blz",
        "beleza",
        "gratidao",
        "agradecido",
        "agradecida",
        "show",
        "top",
        "maravilha",
        "excelente",
        "legal",
        "massa",
        "joia",
    }
)
_FILLER_TOKENS = frozenset(
    {
        "muito",
        "bem",
        "mesmo",
        "entao",
        "ta",
        "tudo",
        "demais",
        "ai",
        "viu",
        "hein",
        "e",
        "eh",
        "sim",
        "agora",
        "por",
        "isso",
        "mas",
        "pela",
        "pelo",
        "tao",
        "de",
        "ja",
    }
)

_SMALLTALK_WORD_RE = re.compile(r"[a-z]+")


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def is_smalltalk(text: str) -> bool:
    """True when the message is a pure acknowledgment / thanks / closing with no
    real question — e.g. "entendi obrigada", "valeu!", "muito obrigado mesmo".
    Such messages should get a brief reply with no retrieved passages, never
    doctrinal source chips. Conservative on purpose (see _ACK_TOKENS): every word
    must be an ack or filler token, there must be no "?", and at least one word
    must be an actual acknowledgment (so bare filler like "sim" doesn't match)."""
    if not text or "?" in text:
        return False
    words = _SMALLTALK_WORD_RE.findall(_strip_accents(text.lower()))
    if not words or len(words) > 6:
        return False
    if not all(w in _ACK_TOKENS or w in _FILLER_TOKENS for w in words):
        return False
    return any(w in _ACK_TOKENS for w in words)


def extract_study_reference(question: str) -> dict:
    """Extract the item number and book from an item-lookup question, so the
    client can open /study directly instead of re-parsing the text. The book
    is the one explicitly named, or O Livro dos Espíritos for the "questão N"
    / "Q. N" forms (see _ITEM_NUMBER_PATTERNS). Values are None when not
    found."""
    item_number = None
    is_questao = False
    for p, questao_flag in _ITEM_NUMBER_PATTERNS:
        m = p.search(question)
        if m:
            item_number = m.group(1)
            is_questao = questao_flag
            break

    book = None
    for p, canonical in _BOOK_PATTERNS:
        if p.search(question):
            book = canonical
            break
    if book is None and is_questao:
        book = _LIVRO_ESPIRITOS

    return {"item_number": item_number, "book": book}
