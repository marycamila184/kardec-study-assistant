from src.rag.prompt import build_messages

_CHUNK = {
    "content": "A encarnação tem por fim fazê-los progredir.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação dos Espíritos",
        "item_number": "132",
    },
    "distance": 0.4,
}


def test_system_contains_passage_content():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "A encarnação tem por fim" in system


def test_system_contains_book_name():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "O Livro dos Espíritos" in system


def test_messages_ends_with_user_question():
    _, messages = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert messages[-1] == {"role": "user", "content": "O que é reencarnação?"}


def test_history_is_prepended_to_messages():
    history = [
        {"role": "user", "content": "Pergunta anterior"},
        {"role": "assistant", "content": "Resposta anterior"},
    ]
    _, messages = build_messages("Nova pergunta", [_CHUNK], history)
    assert messages[0] == {"role": "user", "content": "Pergunta anterior"}
    assert messages[-1]["content"] == "Nova pergunta"


def test_history_is_capped_at_max_history_turns():
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(20)
    ]
    _, messages = build_messages("fim", [_CHUNK], history, max_history_turns=4)
    assert len(messages) == 5  # 4 history turns + 1 current question


def test_system_prohibits_unsolicited_advice():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "conselho" in system.lower() or "sugest" in system.lower()


def test_system_prohibits_personifying_espiritismo():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "espiritismo" in system.lower()


def test_system_allows_optional_reflective_question():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "pergunta reflexiva" in system.lower()


def test_caveat_instruction_in_system_when_requested():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [], add_caveat=True)
    assert "profissional de saúde" in system


def test_no_caveat_in_system_by_default():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "profissional de saúde" not in system


def test_system_shows_real_item_number():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "Item: 132" in system


def test_system_omits_placeholder_item_number():
    chunk = {
        **_CHUNK,
        "metadata": {**_CHUNK["metadata"], "item_number": "section-3"},
    }
    system, _ = build_messages("O que é reencarnação?", [chunk], [])
    assert "section-3" not in system
    assert "Item:" not in system


def test_system_requires_fontes_marker():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "[FONTES:" in system


def test_system_requires_seguir_marker():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "[SEGUIR:" in system
