from src.rag.explicador_prompt import build_explicador_messages


def test_system_prohibits_personifying_espiritismo():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "espiritismo" in system.lower()


def test_system_allows_historical_context():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "histórico" in system.lower()


def test_system_still_forbids_doctrine_invention():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "nunca invente" in system.lower() or "nunca invente ou altere" in system.lower()


def test_footnote_context_appears_in_system_when_provided():
    system, _ = build_explicador_messages("Trecho.", [], footnote_context="[Nota 1] Explicação de exemplo.")
    assert "Explicação de exemplo." in system


def test_footnote_context_defaults_to_placeholder_when_empty():
    system, _ = build_explicador_messages("Trecho.", [])
    assert "(nenhuma)" in system
