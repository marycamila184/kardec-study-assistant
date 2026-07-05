import re

_STUDY_PATTERNS = [
    re.compile(r"\bquestão\s+\d+", re.IGNORECASE),
    re.compile(r"\bitem\s+\d+", re.IGNORECASE),
    re.compile(r"\bq\.\s*\d+", re.IGNORECASE),
    re.compile(r"explique\s+a\s+questão", re.IGNORECASE),
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


def detect_suggested_mode(question: str) -> str | None:
    if any(p.search(question) for p in _STUDY_PATTERNS):
        return "estudar_obra"
    if any(p.search(question) for p in _SITUATIONAL_PATTERNS):
        return "refletir"
    return None
