"""Loads the prompts from src/rag/prompts/*.md.

They live as Markdown so they can be read and edited without going through
Python string escaping — the product owner refines them, and a prompt spread
across concatenated string literals with trailing backslashes is not something
anyone should have to edit carefully.

Loaded at runtime and cached, with no second copy in the code, so a file and
what the model is told cannot drift apart.

See src/rag/prompts/README.md for what belongs in a prompt and what belongs in
code — the distinction that 2026-07-28 spent a day learning.
"""

import functools
import pathlib

_DIR = pathlib.Path(__file__).parent / "prompts"


@functools.lru_cache(maxsize=None)
def load(name: str) -> str:
    """The prompt text, without the trailing newline every text editor adds.

    Stripped because these are assembled into a larger prompt where a stray
    blank line changes the spacing — and the assembled prompt is compared
    byte-for-byte against a recorded baseline.

    Raises if the file is missing: a prompt that silently becomes empty would
    remove a rule and leave everything still running.
    """
    path = _DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").rstrip("\n")
