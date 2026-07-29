"""Recognising a passage the reader pasted.

The case is from live use: someone pasted a paragraph of A Gênese and wrote
"me explique esse". Today the model cannot discuss text it was never given, and
nobody has checked the paste is really Kardec's.
"""

from src.rag.pasted_quote import find_pasted_source

_PASSAGE = (
    "O perispírito, ou corpo fluídico dos Espíritos, é um dos mais importantes "
    "produtos do fluido cósmico; é uma condensação desse fluido em torno de um "
    "foco de inteligência ou alma. Já vimos que também o corpo carnal tem seu "
    "princípio de origem nesse mesmo fluido condensado e transformado em "
    "matéria tangível."
)

_CHUNKS = [
    {"content": _PASSAGE, "metadata": {"book": "A Gênese", "item_number": "7"}},
    {
        "content": (
            "A prece é um ato de adoração. Orar a Deus é pensar Nele; é "
            "aproximar-se Dele; é pôr-se em comunicação com Ele."
        ),
        "metadata": {"book": "O Livro dos Espíritos", "item_number": "659"},
    },
]


def test_a_pasted_passage_resolves_to_its_item():
    found = find_pasted_source(_PASSAGE + " me explique esse", _CHUNKS)
    assert found["metadata"]["item_number"] == "7"


def test_a_partial_paste_still_resolves():
    """Readers paste one paragraph of a longer item, or trim the ending."""
    half = " ".join(_PASSAGE.split()[:30])
    assert find_pasted_source(half + " o que significa?", _CHUNKS) is not None


def test_reflowed_whitespace_and_accents_do_not_matter():
    mangled = _PASSAGE.replace("é", "e").replace(" ", "\n  ")
    assert find_pasted_source(mangled + " explique", _CHUNKS) is not None


def test_an_ordinary_question_resolves_to_nothing():
    assert (
        find_pasted_source("o que é o perispírito e como ele funciona?", _CHUNKS)
        is None
    )


def test_a_long_question_that_merely_resembles_a_passage_is_not_a_paste():
    """Retrieval returns something for everything; only literal containment is
    evidence that this text is what the reader is holding."""
    similar = (
        "queria entender melhor essa ideia de que o perispírito seria uma "
        "espécie de condensação de fluido em volta da alma, porque li algo "
        "parecido em outro lugar e não sei se é a mesma coisa que Kardec diz "
        "ou se é invenção de outro autor mais recente"
    )
    assert find_pasted_source(similar, _CHUNKS) is None


def test_no_chunks_resolves_to_nothing():
    assert find_pasted_source(_PASSAGE, []) is None


def test_the_closest_passage_wins_when_several_overlap():
    chunks = _CHUNKS + [
        {
            "content": _PASSAGE + " E mais uma frase que o leitor não colou.",
            "metadata": {"book": "A Gênese", "item_number": "7-bis"},
        }
    ]
    found = find_pasted_source(_PASSAGE + " explique", chunks)
    assert found["metadata"]["item_number"] in {"7", "7-bis"}
