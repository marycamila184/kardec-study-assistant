"""The marker protocol: flat uppercase `NOME: valor` sections the prose models
emit and code parses deterministically.

Chosen over JSON because an 8B model holds a flat format far more reliably than
a nested one, and because /chat already proved the pattern with [FONTES]/[SEGUIR].

Every pattern here is uppercase-only (no re.IGNORECASE) so ordinary prose
("as fontes:") is never mistaken for a marker.
"""

import re
from typing import Sequence

# Anchored to end of string; the body stops at a newline so two trailer markers
# on separate lines are matched one per loop pass. Tolerant of the model
# mangling the trailer: optional leading "[" or stray "/", optional closing "]",
# whitespace around the colon, a trailing period.
_FONTES_MARKER = re.compile(r"\s*[\[/]?\s*FONTES\s*:\s*([^\]\n]*)\]?\s*\.?\s*$")
_SEGUIR_MARKER = re.compile(r"\s*[\[/]?\s*SEGUIR\s*:\s*([^\]\n]*)\]?\s*\.?\s*$")

# --- prose-lane-only debris cleanup -----------------------------------------
#
# The current provider always emits well-formed trailing markers (handled
# above). The fine-tuned prose-lane model (riv-ai-v2) instead scatters marker
# lines mid-text, prefixed with emoji decoration ("📖 [FONTES: ...]"), and
# leaves stray decoration-only lines ("👉") behind. strip_marker_debris is a
# prose-lane-only pass — it is NOT a replacement for strip_trailing_markers
# and must never be applied to the current provider's output.

# A marker line: arbitrary leading decoration (emoji/punctuation/whitespace,
# optional "[" or "/"), the uppercase keyword, then anything to end of line.
_DEBRIS_FONTES_LINE = re.compile(r"^[^\w\n]*[\[/]?[^\w\n]*FONTES\s*:.*$", re.MULTILINE)
_DEBRIS_SEGUIR_LINE = re.compile(
    r"^[^\w\n]*[\[/]?[^\w\n]*SEGUIR\s*:\s*([^\]\n]*)\]?[^\n]*$", re.MULTILINE
)
# A line with no letters or digits anywhere — pure emoji/punctuation/whitespace.
_DECORATION_ONLY_LINE = re.compile(r"^[^\w\n]*$", re.MULTILINE)


def strip_marker_debris(answer: str) -> tuple[str, list[str]]:
    """Prose-lane-only cleanup for marker text that leaked into the displayed
    answer. Unlike strip_trailing_markers (anchored to end-of-string, used by
    the current provider), this scans the WHOLE text for FONTES/SEGUIR lines
    — wherever the model placed them — tolerates emoji/punctuation decoration
    in front of the keyword, and also removes lines that are pure decoration
    (no letters or digits), such as a stray "👉" left after the marker line
    itself was removed.

    Returns (cleaned_answer, suggested_questions) — suggestions come from a
    SEGUIR line if present (capped at 2), else []. Never raises on empty
    input.
    """
    if not answer:
        return "", []

    suggestions: list[str] = []
    seguir_match = _DEBRIS_SEGUIR_LINE.search(answer)
    if seguir_match:
        suggestions = split_pipe_list(seguir_match.group(1), limit=2)

    text = _DEBRIS_SEGUIR_LINE.sub("", answer)
    text = _DEBRIS_FONTES_LINE.sub("", text)

    lines = [line for line in text.split("\n") if not _DECORATION_ONLY_LINE.match(line)]
    cleaned = "\n".join(lines)
    # Collapse the blank-line runs left behind by removed lines.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(), suggestions


def split_pipe_list(body: str, limit: int | None = None) -> list[str]:
    """Splits a `"a | b | c"` marker body into trimmed, non-empty items."""
    items = [p.strip() for p in body.split("|") if p.strip()]
    return items[:limit] if limit else items


def parse_sections(text: str, names: Sequence[str]) -> dict[str, str]:
    """Parses flat `NOME: valor` sections. A section body runs until the next
    known marker or end of text. Missing sections map to "" so callers never
    KeyError on a model that skipped one."""
    alternation = "|".join(re.escape(n) for n in names)
    # A marker starts at a line start, optionally wrapped in [ ] or prefixed by /.
    # Case-insensitive because the model writes "Contexto:" as readily as
    # "CONTEXTO:", but anchored to line start so mid-sentence prose
    # ("as fontes:") is never swallowed as a section.
    marker = re.compile(
        rf"^[ \t]*[\[/]?[ \t]*({alternation})[ \t]*\]?[ \t]*:[ \t]*",
        re.MULTILINE | re.IGNORECASE,
    )
    matches = list(marker.finditer(text))
    # Keys are normalized to the caller's spelling, whatever case the model used.
    canonical = {n.upper(): n for n in names}
    out = {name: "" for name in names}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip()
        # Strip a trailing "]" left by a model that wrote [PERGUNTAS: a | b]
        out[canonical[m.group(1).upper()]] = body.rstrip("]").strip()
    return out


def _cited_chunks(marker_body: str, chunks: list[dict]) -> list[dict]:
    """Resolves the [FONTES: 1, 3] body to the chunks the model says it used
    (1-based indices matching the prompt's passage numbering). Fallbacks keep
    the citation chips honest without ever losing them to a malformed marker:
    - marker with only invalid indices → all chunks;
    - explicitly empty marker → no sources (the model used none).
    """
    indices = [int(t) for t in re.findall(r"\d+", marker_body)]
    if not indices:
        return []
    cited = [c for i, c in enumerate(chunks, 1) if i in set(indices)]
    return cited or chunks


def strip_trailing_markers(
    answer: str, chunks: list[dict]
) -> tuple[str, list[dict], list[str]]:
    """Strips the prompt-mandated [FONTES] and [SEGUIR] trailer lines off the
    answer, in whichever order the model emitted them. Returns
    (answer, cited_chunks, suggested_questions); a missing marker leaves its
    output at the safe default (all chunks / no suggestions)."""
    suggestions: list[str] = []
    for _ in range(2):
        m = _SEGUIR_MARKER.search(answer)
        if m:
            answer = answer[: m.start()].rstrip()
            suggestions = split_pipe_list(m.group(1), limit=2)
            continue
        m = _FONTES_MARKER.search(answer)
        if m:
            answer = answer[: m.start()].rstrip()
            chunks = _cited_chunks(m.group(1), chunks)
            continue
        break
    return answer, chunks, suggestions
