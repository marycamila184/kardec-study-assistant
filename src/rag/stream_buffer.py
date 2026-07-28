"""Holds back text that might still grow into a trailer marker, so the machine
-readable `[FONTES: ...]` / `[SEGUIR: ...]` sections never reach the screen
while the answer is streaming.

The buffer is content-aware rather than a fixed-size window: it emits prose the
moment it is unambiguous, and the instant an opening looks like it is forming it
stops emitting entirely. A fixed window could not hold this guarantee — the
follow-up questions in `[SEGUIR]` are arbitrarily long, so `[FONTES]` would
slide out of any window sized in advance.

Sealing on the first opening is safe because the markers are trailer-only by
contract (see src/rag/prompt.py): everything from the first one onwards belongs
to the trailer, not to the answer. `flush()` hands that tail back so the caller
can run the normal post-processing on the complete text.

See docs/superpowers/specs/2026-07-27-streaming-design.md
"""

# Uppercase-only, matching src/rag/markers.py — ordinary prose ("as fontes
# citadas") must never be mistaken for a marker and held back.
_KEYWORDS = ("FONTES", "SEGUIR")

# The shapes a marker can open with, tolerating the mangling markers.py already
# tolerates: an optional "[" or stray "/", and an optional space after it.
# There is deliberately no bare " FONTES" (space, no bracket) opening: the
# unprefixed "FONTES" already catches that case one character later, whereas
# treating a lone space as a marker-in-the-making would hold back every space
# in ordinary prose.
_OPENINGS = tuple(
    lead + keyword for lead in ("", "[", "/", "[ ", "/ ") for keyword in _KEYWORDS
)

_MAX_OPENING = max(len(opening) for opening in _OPENINGS)


class StreamBuffer:
    """Feed it model output in whatever chunks arrive; it returns the slice that
    is safe to put on screen. Stateful and single-use per response."""

    def __init__(self) -> None:
        self._held = ""
        self._sealed = False

    def feed(self, chunk: str) -> str:
        """Returns the text safe to emit now. Everything not returned is held."""
        if self._sealed:
            self._held += chunk
            return ""

        pending = self._held + chunk

        start = self._find_opening(pending)
        if start is not None:
            self._sealed = True
            self._held = pending[start:]
            return pending[:start]

        # No marker yet, but the tail may be one in the making. Hold the longest
        # suffix that could still grow into an opening; emit everything before it.
        for i in range(max(0, len(pending) - _MAX_OPENING + 1), len(pending)):
            if any(opening.startswith(pending[i:]) for opening in _OPENINGS):
                self._held = pending[i:]
                return pending[:i]

        self._held = ""
        return pending

    def flush(self) -> str:
        """Returns what is still held — the trailer, plus any prose that was
        awaiting disambiguation when the stream ended."""
        held, self._held = self._held, ""
        return held

    @staticmethod
    def _find_opening(text: str) -> int | None:
        positions = [text.find(opening) for opening in _OPENINGS]
        found = [p for p in positions if p != -1]
        return min(found) if found else None
