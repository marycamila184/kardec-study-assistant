"""Quoted text attributed to the works must exist in the works.

The case these tests were written from is real, from production on 2026-07-28:
asked about "duplo etéreo ou aura", the model invented a sentence, quoted it,
and attributed it to Kardec with a chapter and an item.

The opposite failure matters just as much. A guard that flags honest quotations
— reflowed whitespace, modernised spelling, a changed comma — trains everyone to
ignore it, and then it protects nobody.
"""

from src.rag.quote_check import find_unsupported_quotes

_CHUNKS = [
    {
        "content": (
            "O perispírito desempenha preponderante papel no organismo. "
            "Pela sua união íntima com o corpo, põe o Espírito encarnado em "
            "relação mais direta com os Espíritos livres."
        )
    },
    {
        "content": (
            "É nas propriedades e nas irradiações do fluido perispirítico que "
            "se tem de procurar a causa da dupla vista, ou vista espiritual, "
            "da qual muitas pessoas são dotadas, freqüentemente a seu mau grado."
        )
    },
]


def test_the_production_failure_is_caught():
    answer = (
        'Kardec escreve que "o duplo etéreo é uma espécie de envoltório '
        'fluídico que envolve o corpo físico e é uma extensão do perispírito" '
        "(A Gênese, capítulo OS FLUIDOS, item 18)."
    )
    found = find_unsupported_quotes(answer, _CHUNKS)
    assert len(found) == 1
    assert "duplo etéreo" in found[0]


def test_a_real_quotation_passes():
    answer = (
        'A passagem diz: "O perispírito desempenha preponderante papel no '
        'organismo."'
    )
    assert find_unsupported_quotes(answer, _CHUNKS) == []


def test_reflowed_whitespace_is_not_fabrication():
    answer = (
        'Kardec escreve que "O perispírito   desempenha preponderante\n'
        'papel no organismo."'
    )
    assert find_unsupported_quotes(answer, _CHUNKS) == []


def test_modernised_spelling_is_not_fabrication():
    """The works are 1860s editions; the model silently fixes 'freqüentemente'."""
    answer = '"da qual muitas pessoas são dotadas, frequentemente a seu mau grado"'
    assert find_unsupported_quotes(answer, _CHUNKS) == []


def test_curly_quotes_and_guillemets_are_read():
    answer = "Kardec escreve que “o duplo etéreo envolve o corpo físico humano”."
    assert len(find_unsupported_quotes(answer, _CHUNKS)) == 1


def test_short_quoted_terms_are_ignored():
    """Scare quotes around a term are not a claim about what the text says."""
    answer = 'Isso é uma espécie de "campo de energia" que rodeia o corpo.'
    assert find_unsupported_quotes(answer, _CHUNKS) == []


def test_punctuation_differences_are_tolerated():
    answer = '"O perispírito desempenha preponderante papel no organismo"'
    assert find_unsupported_quotes(answer, _CHUNKS) == []


def test_several_fabrications_are_all_reported_in_order():
    answer = (
        '"a primeira frase inventada que ninguém escreveu jamais" e também '
        '"a segunda frase inventada que ninguém escreveu jamais"'
    )
    found = find_unsupported_quotes(answer, _CHUNKS)
    assert len(found) == 2
    assert found[0].startswith("a primeira")


def test_no_chunks_means_every_long_quote_is_unsupported():
    answer = '"uma frase qualquer atribuída às obras de Allan Kardec"'
    assert len(find_unsupported_quotes(answer, [])) == 1


def test_empty_answer():
    assert find_unsupported_quotes("", _CHUNKS) == []
