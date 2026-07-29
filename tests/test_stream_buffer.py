"""The hold-back buffer that stands between the model's tokens and the screen.

The invariant these tests exist to protect is the one from the streaming plan:
no `token` event may ever contain `FONTES` or `SEGUIR`. Everything else here
is in service of not paying for that guarantee with held-back prose.

See docs/superpowers/specs/2026-07-27-streaming-design.md
"""

from src.rag.stream_buffer import StreamBuffer

_ANSWER = "Kardec escreve que o espírito sobrevive ao corpo."
_TRAILER = "[FONTES: 1, 3][SEGUIR: O que é perispírito? | E a reencarnação?]"


def _feed_char_by_char(text: str) -> tuple[str, str]:
    """Returns (everything emitted, what flush left over)."""
    buf = StreamBuffer()
    emitted = "".join(buf.feed(ch) for ch in text)
    return emitted, buf.flush()


def test_plain_prose_is_emitted_as_it_arrives():
    buf = StreamBuffer()
    assert buf.feed("Kardec escreve ") == "Kardec escreve "
    assert buf.feed("que o espírito ") == "que o espírito "
    assert buf.flush() == ""


def test_marker_fed_character_by_character_never_reaches_the_screen():
    emitted, _ = _feed_char_by_char(_ANSWER + "[FONTES: 1, 3]")

    assert "FONTES" not in emitted
    assert "[" not in emitted


def test_marker_split_across_two_chunks_never_reaches_the_screen():
    buf = StreamBuffer()
    emitted = buf.feed(_ANSWER + "[FON") + buf.feed("TES: 1]")

    assert "FONTES" not in emitted
    assert "FON" not in emitted


def test_both_trailer_markers_are_held_however_long_the_seguir_body_is():
    """A fixed-size window would let [FONTES] slide out while [SEGUIR] is still
    arriving. Nothing may leak, no matter how long the follow-up questions are."""
    emitted, _ = _feed_char_by_char(_ANSWER + _TRAILER)

    assert "FONTES" not in emitted
    assert "SEGUIR" not in emitted


def test_flush_returns_the_held_trailer_for_post_processing():
    buf = StreamBuffer()
    buf.feed(_ANSWER + _TRAILER)

    assert buf.flush() == _TRAILER


def test_emitted_text_plus_flush_reconstructs_the_input_exactly():
    """The `done` event's answer is post-processed from the full text, so the
    buffer must never lose or duplicate a character."""
    text = _ANSWER + _TRAILER
    emitted, leftover = _feed_char_by_char(text)

    assert emitted + leftover == text


def test_lowercase_fontes_in_ordinary_prose_is_not_held_back():
    """Markers are uppercase-only; ordinary prose must not be retained forever."""
    buf = StreamBuffer()
    emitted = buf.feed("As fontes citadas pelo autor são claras.")

    assert emitted == "As fontes citadas pelo autor são claras."
    assert buf.flush() == ""


def test_a_bracket_that_turns_out_to_be_prose_is_released():
    """Holding on '[' is fine; holding it forever is not."""
    buf = StreamBuffer()
    emitted = buf.feed("o texto [nota do tradutor] segue")

    assert emitted == "o texto [nota do tradutor] segue"


def test_flush_is_empty_when_nothing_was_ever_fed():
    assert StreamBuffer().flush() == ""
