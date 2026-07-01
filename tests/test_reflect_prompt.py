from src.rag.reflect_prompt import (
    build_reflect_messages,
    needs_medical_caveat,
    parse_reflect_json,
)

_CHUNK = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {"book": "O Livro dos Espíritos", "item_number": "150"},
    "distance": 0.3,
}


def test_needs_medical_caveat_true_for_vozes():
    assert needs_medical_caveat("escuto vozes à noite") is True


def test_needs_medical_caveat_true_for_sombras():
    assert needs_medical_caveat("estou vendo sombras") is True


def test_needs_medical_caveat_false_for_normal_situation():
    assert needs_medical_caveat("meu pai faleceu") is False


def test_caveat_instruction_in_system_when_needed():
    system, _ = build_reflect_messages("escuto vozes", [], add_caveat=True)
    assert "profissional de saúde" in system


def test_no_caveat_in_system_when_not_needed():
    system, _ = build_reflect_messages("meu pai faleceu", [], add_caveat=False)
    assert "profissional de saúde" not in system


def test_no_advice_constraint_in_system():
    system, _ = build_reflect_messages("qualquer situação", [], add_caveat=False)
    assert "absolutamente proibido" in system


def test_situation_text_appears_in_system():
    system, _ = build_reflect_messages("meu casamento está difícil", [], add_caveat=False)
    assert "meu casamento está difícil" in system


def test_system_prohibits_personifying_espiritismo():
    system, _ = build_reflect_messages("qualquer situação", [], add_caveat=False)
    assert "espiritismo" in system.lower()


def test_chunk_content_appears_in_system():
    system, _ = build_reflect_messages("situação", [_CHUNK], add_caveat=False)
    assert "Os espíritos sobrevivem" in system


def test_messages_contains_single_user_message():
    _, messages = build_reflect_messages("situação", [], add_caveat=False)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


def test_parse_reflect_json_extracts_all_fields():
    text = '{"opening": "Sentimos sua dor.", "doctrine_connection": "A doutrina diz...", "reflection_questions": ["Q1?", "Q2?", "Q3?"]}'
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "Sentimos sua dor."
    assert conn == "A doutrina diz..."
    assert questions == ["Q1?", "Q2?", "Q3?"]


def test_parse_reflect_json_strips_markdown_fences():
    text = '```json\n{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"]}\n```'
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "A."
    assert conn == "B."
    assert questions == ["C?"]


def test_parse_reflect_json_falls_back_on_invalid_json():
    text = "não é JSON válido"
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "não é JSON válido"
    assert conn == ""
    assert questions == []
