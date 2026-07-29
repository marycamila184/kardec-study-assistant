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
