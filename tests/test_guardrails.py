from src.rag.guardrails import counts_personification, strip_trailing_question


def test_strips_a_trailing_question():
    text = "A caridade é o essencial. O que isso significa para você?"
    assert strip_trailing_question(text) == "A caridade é o essencial."


def test_strips_trailing_question_across_newline():
    text = "A caridade é o essencial.\n\nJá pensou nisso?"
    assert strip_trailing_question(text) == "A caridade é o essencial."


def test_leaves_statement_ending_untouched():
    text = "A caridade é o essencial da doutrina."
    assert strip_trailing_question(text) == text


def test_keeps_mid_text_questions():
    """Only the closing question is the violation; quoted questions stay."""
    text = 'O texto pergunta: "que é o espírito?" e responde em seguida.'
    assert strip_trailing_question(text) == text


def test_does_not_empty_an_all_question_answer():
    """A single-sentence question must not be stripped to nothing."""
    text = "O que é o espírito?"
    assert strip_trailing_question(text) == text


def test_counts_personification():
    text = "O Espiritismo valoriza a caridade. O Espiritismo diz que a alma persiste."
    assert counts_personification(text) == 2


def test_attributed_claims_are_not_personification():
    text = "Esta passagem mostra que a caridade é essencial no Espiritismo."
    assert counts_personification(text) == 0
