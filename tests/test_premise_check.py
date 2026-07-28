"""Terms a question introduces that the works never use.

The case: "isso influencia o meu ectoplasma e a minha aura" got a confident
doctrinal answer, while "o que Kardec fala sobre a aura" correctly got nothing.
Same absent concept — the difference was the premise being embedded.
"""

from src.rag.premise_check import unsupported_terms

# A stand-in corpus, so these tests do not depend on data/markdown_files being
# present. What is measured against the real works is the probe script.
_VOCABULARY = (
    "o perispirito desempenha preponderante papel no organismo e funciona "
    "como laco. a prece e um ato de adoracao. a caridade e a lei. o fluido "
    "perispiritico e a dupla vista. o perdao das faltas."
)

_CHUNKS = [
    {
        "content": (
            "O perispírito desempenha preponderante papel no organismo. "
            "É nas propriedades e nas irradiações do fluido perispirítico que "
            "se tem de procurar a causa da dupla vista."
        )
    },
    {"content": "A prece é um ato de adoração. Orar a Deus é pensar Nele."},
]


def test_the_production_case_is_flagged():
    found = unsupported_terms(
        "isso influencia o meu ectoplasma e a minha aura", _CHUNKS
    )
    assert "ectoplasma" in found


def test_a_generic_word_absent_from_the_passages_is_not_a_premise():
    """'funciona' and 'papel' were flagged when only the retrieved chunks were
    checked — ordinary words, long enough to pass the filter, absent from those
    particular passages and present throughout Kardec."""
    assert unsupported_terms("como funciona o papel disso?", _CHUNKS, _VOCABULARY) == []


def test_a_term_the_works_use_is_not_flagged():
    assert unsupported_terms("o que é o perispírito?", _CHUNKS) == []


def test_a_related_word_form_counts_as_present():
    """'perispirítico' must satisfy 'perispírito' — a stemmer would be a second
    thing to get wrong, and a false 'absent' is the expensive direction."""
    assert "perispirito" not in unsupported_terms(
        "fale do perispírito", _CHUNKS, _VOCABULARY
    )


def test_common_words_are_not_treated_as_premises():
    found = unsupported_terms(
        "o que Kardec diz sobre isso na doutrina?", _CHUNKS, _VOCABULARY
    )
    assert found == []


def test_accents_and_case_do_not_matter():
    assert unsupported_terms("A PRECE é adoração?", _CHUNKS) == []


def test_several_absent_terms_are_all_reported():
    found = unsupported_terms(
        "fale sobre chakras e cristais energéticos", _CHUNKS, _VOCABULARY
    )
    assert "chakras" in found
    assert "cristais" in found


def test_no_chunks_reports_nothing():
    """With nothing retrieved the not-found path already handles it; flagging
    every word here would just be noise."""
    assert unsupported_terms("qualquer coisa", [], _VOCABULARY) == []
