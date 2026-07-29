"""System vocabulary must not reach the reader.

The prompt forbids these expressions by name, with an example. On 2026-07-28 an
answer used one anyway. A closed list is what makes this checkable in code.
"""

from src.rag.guardrails import strip_internal_terms


def test_the_production_leak_is_rewritten():
    text = "as passagens recuperadas não contêm informações suficientes."
    out, count = strip_internal_terms(text)
    assert out == "as obras não contêm informações suficientes."
    assert count == 1


def test_the_preposition_is_preserved():
    """'nas passagens recuperadas' must not become 'nas as obras'."""
    out, _ = strip_internal_terms("não há menção nas passagens recuperadas.")
    assert out == "não há menção nas obras."
    assert "nas as" not in out


def test_every_listed_expression_is_covered():
    for phrase in (
        "as passagens recuperadas",
        "os trechos fornecidos",
        "o material acima",
        "os textos fornecidos",
    ):
        out, count = strip_internal_terms(f"Segundo {phrase}, isso é verdade.")
        assert count == 1, phrase
        assert phrase not in out.lower(), phrase


def test_case_is_ignored_but_the_sentence_survives():
    out, count = strip_internal_terms("As Passagens Recuperadas mostram isso.")
    assert count == 1
    assert "mostram isso." in out


def test_ordinary_prose_is_untouched():
    text = "Kardec escreve que as obras tratam da imortalidade da alma."
    out, count = strip_internal_terms(text)
    assert out == text
    assert count == 0


def test_the_word_passagem_alone_is_not_a_leak():
    """'a passagem mostra que' is the attribution the prompt asks for."""
    text = "A passagem mostra que o espírito sobrevive ao corpo."
    out, count = strip_internal_terms(text)
    assert out == text
    assert count == 0


def test_counts_every_occurrence():
    text = "as passagens recuperadas e os trechos fornecidos dizem o mesmo."
    _, count = strip_internal_terms(text)
    assert count == 2
