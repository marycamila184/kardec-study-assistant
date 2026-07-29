"""Fabricated quotations must never be shown, not even for a moment.

Found in production 2026-07-28: the guard ran after generation, so an invented
quotation streamed onto the screen in full and was replaced only when `done`
arrived. The reader watched it being written and then saw it vanish.
"""

from src.rag.quote_check import StreamingQuoteGuard

_CHUNKS = [
    {
        "content": (
            "O perispírito desempenha preponderante papel no organismo. "
            "Pela sua união íntima com o corpo, põe o Espírito encarnado em "
            "relação mais direta com os Espíritos livres."
        )
    }
]


def _stream(text: str, size: int = 3):
    guard = StreamingQuoteGuard(_CHUNKS)
    shown = ""
    for i in range(0, len(text), size):
        shown += guard.feed(text[i : i + size])
        if guard.violated:
            return shown, guard
    return shown + guard.flush(), guard


def test_an_invented_quotation_never_reaches_the_screen():
    text = 'Kardec escreve que "a aura é o espelho do estado espiritual do ser".'
    shown, guard = _stream(text)
    assert guard.violated
    assert "aura é o espelho" not in shown


def test_a_real_quotation_is_released_whole():
    text = 'A passagem diz "O perispírito desempenha preponderante papel no organismo." e segue.'
    shown, guard = _stream(text)
    assert not guard.violated
    assert "preponderante papel no organismo" in shown


def test_prose_outside_quotations_flows_normally():
    text = "Kardec escreve que o perispírito liga o Espírito ao corpo."
    shown, guard = _stream(text)
    assert shown == text
    assert not guard.violated


def test_short_quoted_terms_do_not_stall_or_trip_the_guard():
    text = 'É uma espécie de "campo" que rodeia o corpo físico do ser humano.'
    shown, guard = _stream(text)
    assert not guard.violated
    assert shown == text


def test_a_quotation_that_never_closes_is_returned_as_prose():
    text = 'Kardec escreve que "isto ficou sem fechar'
    shown, guard = _stream(text)
    assert not guard.violated
    assert shown == text


def test_nothing_is_emitted_after_a_violation():
    text = 'Antes. "uma citação inteiramente inventada que ninguém escreveu". Depois.'
    shown, guard = _stream(text)
    assert guard.violated
    assert "Depois" not in shown


def test_the_offending_text_is_reported_for_the_log():
    text = '"uma citação inteiramente inventada que ninguém jamais escreveu"'
    _, guard = _stream(text)
    assert guard.offending.startswith("uma citação")
