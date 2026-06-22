import re

_STUDY_PATTERNS = [
    re.compile(r"\bquestão\s+\d+", re.IGNORECASE),
    re.compile(r"\bitem\s+\d+", re.IGNORECASE),
    re.compile(r"\bq\.\s*\d+", re.IGNORECASE),
    re.compile(r"explique\s+a\s+questão", re.IGNORECASE),
    re.compile(r"o\s+que\s+(diz|fala)\s+.+\d+", re.IGNORECASE),
]


def detect_suggested_mode(question: str) -> str | None:
    if any(p.search(question) for p in _STUDY_PATTERNS):
        return "estudar_obra"
    return None
