from src.rag.reflect_prompt import (
    CRISIS_NOTE,
    build_reflect_messages,
    needs_crisis_note,
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
    system, _ = build_reflect_messages(
        "meu casamento está difícil", [], add_caveat=False
    )
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
    opening, conn, questions, is_closing = parse_reflect_json(text)
    assert opening == "Sentimos sua dor."
    assert conn == "A doutrina diz..."
    assert questions == ["Q1?", "Q2?", "Q3?"]
    assert is_closing is False


def test_parse_reflect_json_strips_markdown_fences():
    text = '```json\n{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"]}\n```'
    opening, conn, questions, is_closing = parse_reflect_json(text)
    assert opening == "A."
    assert conn == "B."
    assert questions == ["C?"]
    assert is_closing is False


def test_parse_reflect_json_raises_on_invalid_json():
    text = "não é JSON válido"
    try:
        parse_reflect_json(text)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_reflect_json_extracts_is_closing_true():
    text = '{"opening": "Encerrando.", "doctrine_connection": "Conclusão.", "reflection_questions": [], "is_closing": true}'
    opening, conn, questions, is_closing = parse_reflect_json(text)
    assert is_closing is True
    assert questions == []


def test_build_reflect_messages_includes_history():
    history = [
        {"role": "user", "content": "Qual pergunta anterior?"},
        {"role": "assistant", "content": "Resposta anterior dada."},
    ]
    system, _ = build_reflect_messages(
        "nova situação", [], add_caveat=False, history=history
    )
    assert "Resposta anterior dada." in system
    assert "Qual pergunta anterior?" in system


def test_build_reflect_messages_history_placeholder_when_empty():
    system, _ = build_reflect_messages("situação", [], add_caveat=False, history=[])
    assert "primeira reflexão" in system


def test_system_prohibits_repeating_previous_questions():
    system, _ = build_reflect_messages("situação", [], add_caveat=False, history=[])
    assert "NUNCA repita" in system


def test_needs_crisis_note_true_for_suicidio():
    assert needs_crisis_note("tenho pensado em suicídio") is True


def test_needs_crisis_note_true_without_accents():
    assert needs_crisis_note("penso em suicidio as vezes") is True


def test_needs_crisis_note_true_for_quero_morrer():
    assert needs_crisis_note("às vezes eu quero morrer") is True


def test_needs_crisis_note_true_for_self_harm():
    assert needs_crisis_note("tenho vontade de me machucar") is True


def test_needs_crisis_note_false_for_grief():
    assert needs_crisis_note("meu pai morreu e sinto saudade") is False


def test_needs_crisis_note_false_for_doctrine_question():
    assert needs_crisis_note("o que Kardec diz sobre a morte?") is False


def test_crisis_note_mentions_cvv_hotline():
    assert "CVV" in CRISIS_NOTE
    assert "188" in CRISIS_NOTE


def test_force_closing_directive_in_system_when_forced():
    system, _ = build_reflect_messages(
        "situação", [], add_caveat=False, force_closing=True
    )
    assert "ENCERRAMENTO OBRIGATÓRIO" in system
    assert '"is_closing": true' in system


def test_no_force_closing_directive_by_default():
    system, _ = build_reflect_messages("situação", [], add_caveat=False)
    assert "ENCERRAMENTO OBRIGATÓRIO" not in system


def test_parse_reflect_json_extracts_object_wrapped_in_prose():
    text = (
        "Aqui está o JSON solicitado:\n"
        '{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"]}\n'
        "Espero que ajude!"
    )
    opening, conn, questions, is_closing = parse_reflect_json(text)
    assert opening == "A."
    assert conn == "B."
    assert questions == ["C?"]
    assert is_closing is False


def test_system_allows_one_to_three_questions():
    system, _ = build_reflect_messages("situação", [], add_caveat=False)
    assert "de 1 a 3 perguntas" in system
