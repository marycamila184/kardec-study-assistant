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
