from src.rag.reflect_prompt import build_reflect_messages, parse_reflect_json

_CHUNK = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {"book": "O Livro dos Espíritos", "item_number": "150"},
    "distance": 0.3,
}


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
