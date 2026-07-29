"""Reads one string field out of JSON that is still arriving.

Explicador is pinned to the JSON lane and answers with a structured object, so
there is no prose stream to forward to the screen — the raw deltas are JSON
syntax. This pulls the value of one named field (`contexto`) out of that text as
it accumulates, so the reader sees the explanation being written instead of the
braces around it.

The rule that makes it correct is the one `stream_buffer.py` applies to trailer
markers: never emit anything that might still be incomplete. Providers split
chunks at arbitrary byte offsets, so an escape sequence routinely arrives in two
pieces, and half of a `\\uXXXX` must not reach the screen as literal text.

No LLM and no network: the output is a pure function of the text fed in, which
is how it is tested.
"""

import re

_SEEKING, _IN_STRING, _DONE = "seeking", "in_string", "done"

_SIMPLE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "\\": "\\",
    "/": "/",
}


class JsonFieldStreamer:
    """Feed raw JSON text in; get the decoded text of one string field out.

    Everything before the field, after it, and around it is ignored. Once the
    field's closing quote arrives the streamer is finished and stays silent —
    later fields in the same object are not its business.
    """

    def __init__(self, field: str) -> None:
        # The opening is matched as a whole so a field name appearing inside an
        # earlier string value can't be mistaken for the key itself.
        self._opening = re.compile(r'"%s"\s*:\s*"' % re.escape(field))
        self._state = _SEEKING
        self._buf = ""

    @property
    def finished(self) -> bool:
        return self._state is _DONE

    def feed(self, chunk: str) -> str:
        """Returns the text decoded from this chunk, or "" when nothing can be
        emitted safely yet."""
        self._buf += chunk
        if self._state is _SEEKING:
            match = self._opening.search(self._buf)
            if match is None:
                return ""
            self._buf = self._buf[match.end() :]
            self._state = _IN_STRING
        if self._state is _IN_STRING:
            return self._consume()
        return ""

    def _consume(self) -> str:
        out: list[str] = []
        buf = self._buf
        i = 0
        while i < len(buf):
            ch = buf[i]
            if ch == '"':
                self._state = _DONE
                i += 1
                break
            if ch != "\\":
                out.append(ch)
                i += 1
                continue

            # An escape whose tail hasn't arrived: leave it in the buffer whole
            # and wait. This is the case that makes the class necessary.
            if i + 1 >= len(buf):
                break
            code = buf[i + 1]
            if code != "u":
                out.append(_SIMPLE_ESCAPES.get(code, code))
                i += 2
                continue

            decoded, consumed = self._unicode_escape(buf, i)
            if decoded is None:
                break  # incomplete — including a surrogate missing its pair
            out.append(decoded)
            i += consumed

        self._buf = buf[i:]
        return "".join(out)

    @staticmethod
    def _unicode_escape(buf: str, i: int) -> tuple[str | None, int]:
        """Decodes `\\uXXXX` at buf[i], joining a surrogate pair when there is
        one. Returns (None, 0) when more text is needed."""
        if i + 6 > len(buf):
            return None, 0
        try:
            value = int(buf[i + 2 : i + 6], 16)
        except ValueError:
            # Malformed rather than incomplete: pass it through as written
            # instead of stalling the stream on text that will never parse.
            return buf[i : i + 6], 6
        if not 0xD800 <= value <= 0xDBFF:
            return chr(value), 6

        # High surrogate: the character isn't known until its pair arrives.
        if i + 12 > len(buf):
            return None, 0
        if buf[i + 6 : i + 8] != "\\u":
            return chr(value), 6
        try:
            low = int(buf[i + 8 : i + 12], 16)
        except ValueError:
            return chr(value), 6
        if not 0xDC00 <= low <= 0xDFFF:
            return chr(value), 6
        return chr(0x10000 + ((value - 0xD800) << 10) + (low - 0xDC00)), 12
