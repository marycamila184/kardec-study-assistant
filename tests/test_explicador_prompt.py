from src.rag.explicador_prompt import build_explicador_messages


def test_system_prohibits_personifying_espiritismo():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "espiritismo" in system.lower()
