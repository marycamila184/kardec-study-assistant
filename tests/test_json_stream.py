"""Reading one field out of JSON that is still arriving.

The invariant these tests protect: what comes out must not depend on where the
provider happened to split its chunks. A `\\uXXXX` cut in half must never reach
the screen as literal text.

See docs/superpowers/specs/2026-07-28-study-trecho-streaming-design.md
"""

import json

import pytest

from src.rag.json_stream import JsonFieldStreamer


def _feed_in_pieces(raw: str, size: int, field: str = "contexto") -> str:
    streamer = JsonFieldStreamer(field)
    return "".join(streamer.feed(raw[i : i + size]) for i in range(0, len(raw), size))


def test_reads_the_field_from_a_whole_document():
    raw = json.dumps({"contexto": "Kardec escreve que o espírito sobrevive."})
    assert JsonFieldStreamer("contexto").feed(raw) == (
        "Kardec escreve que o espírito sobrevive."
    )


@pytest.mark.parametrize("size", range(1, 25))
def test_output_is_independent_of_chunk_size(size):
    """The heart of it: same JSON, every possible split, same text out."""
    text = 'Kardec diz: "o espírito é imortal".\nA questão 150 trata disso.'
    raw = json.dumps(
        {"contexto": text, "conceitos_chave": ["imortalidade"]}, ensure_ascii=False
    )
    assert _feed_in_pieces(raw, size) == text


@pytest.mark.parametrize("size", range(1, 12))
def test_escaped_unicode_split_across_chunks(size):
    """ensure_ascii=True turns every accent into \\uXXXX — routine here, since
    the source texts are Portuguese."""
    text = "A reencarnação é uma consequência da imortalidade."
    raw = json.dumps({"contexto": text})  # ensure_ascii=True by default
    assert "\\u" in raw
    assert _feed_in_pieces(raw, size) == text


@pytest.mark.parametrize("size", range(1, 9))
def test_surrogate_pair_is_never_emitted_half_decoded(size):
    text = "Um emoji 🕊 no meio do texto."
    raw = json.dumps({"contexto": text})
    out = _feed_in_pieces(raw, size)
    assert out == text
    assert "\ud83d" not in out  # no lone high surrogate reached the caller


def test_embedded_quotes_and_newlines_survive():
    text = 'Ele pergunta: "o que é o perispírito?"\n\nE responde em seguida.'
    raw = json.dumps({"contexto": text}, ensure_ascii=False)
    assert _feed_in_pieces(raw, 3) == text


def test_stops_at_the_closing_quote_and_ignores_later_fields():
    raw = json.dumps(
        {"contexto": "Só isto.", "perguntas": ["Não isto."]}, ensure_ascii=False
    )
    streamer = JsonFieldStreamer("contexto")
    assert streamer.feed(raw) == "Só isto."
    assert streamer.finished
    assert streamer.feed('"perguntas": "mais texto"') == ""


def test_ignores_the_field_name_appearing_inside_an_earlier_value():
    raw = json.dumps(
        {"original": 'a palavra "contexto": não é a chave', "contexto": "O certo."},
        ensure_ascii=False,
    )
    assert JsonFieldStreamer("contexto").feed(raw) == "O certo."


def test_silent_until_the_field_appears():
    streamer = JsonFieldStreamer("contexto")
    assert streamer.feed('{"conceitos_chave": ["a", "b"], ') == ""
    assert streamer.feed('"contexto": "Agora sim.') == "Agora sim."


def test_missing_field_emits_nothing_rather_than_guessing():
    raw = json.dumps({"conceitos_chave": ["imortalidade"], "perguntas": []})
    streamer = JsonFieldStreamer("contexto")
    assert streamer.feed(raw) == ""
    assert not streamer.finished


def test_whitespace_between_key_and_value():
    assert JsonFieldStreamer("contexto").feed('{"contexto"  :   "texto"}') == "texto"


def test_malformed_unicode_escape_does_not_stall_the_stream():
    """Text that will never parse must not hold the reader's screen hostage."""
    out = JsonFieldStreamer("contexto").feed('{"contexto": "antes \\uZZZZ depois"}')
    assert out.startswith("antes ")
    assert out.endswith(" depois")
