from src.rag.guardrails import counts_personification


def test_counts_personification():
    text = "O Espiritismo valoriza a caridade. O Espiritismo diz que a alma persiste."
    assert counts_personification(text) == 2


def test_attributed_claims_are_not_personification():
    text = "Esta passagem mostra que a caridade é essencial no Espiritismo."
    assert counts_personification(text) == 0
