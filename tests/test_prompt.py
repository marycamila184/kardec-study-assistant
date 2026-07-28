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


def test_system_forbids_closing_with_inline_question():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "Não encerre o texto da resposta com uma pergunta" in system


def test_system_forbids_repeating_asked_questions_in_seguir():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "já foi feita ou já foi respondida" in system


def test_caveat_instruction_in_system_when_requested():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [], add_caveat=True)
    assert "profissional de saúde" in system


def test_no_caveat_in_system_by_default():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "profissional de saúde" not in system


def test_system_shows_real_item_number():
    # _CHUNK is O Livro dos Espíritos, whose entries are questões — the header
    # is where the model learns that vocabulary, and it echoes it into prose.
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "Questão: 132" in system
    assert "Item: 132" not in system


def test_system_calls_other_works_itens():
    chunk = {**_CHUNK, "metadata": {**_CHUNK["metadata"], "book": "A Gênese"}}
    system, _ = build_messages("O que é reencarnação?", [chunk], [])
    assert "Item: 132" in system
    assert "Questão" not in system


def test_system_omits_placeholder_item_number():
    chunk = {
        **_CHUNK,
        "metadata": {**_CHUNK["metadata"], "item_number": "section-3"},
    }
    system, _ = build_messages("O que é reencarnação?", [chunk], [])
    assert "section-3" not in system
    assert "Item:" not in system
    assert "Questão:" not in system


def test_system_requires_fontes_marker():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "[FONTES:" in system


def test_system_requires_seguir_marker():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "[SEGUIR:" in system


_PROMPT_CHUNK = {
    "content": "texto doutrinário",
    "metadata": {"book": "O Livro dos Espíritos", "item_number": "1"},
}


def test_build_messages_sensitive_adds_gentle_instruction():
    system, _ = build_messages("estou mal", [_PROMPT_CHUNK], [], sensitive=True)
    assert "acolhimento" in system


def test_build_messages_not_sensitive_omits_gentle_instruction():
    system, _ = build_messages("o que é X?", [_PROMPT_CHUNK], [], sensitive=False)
    assert "acolhimento" not in system


def test_the_passage_header_carries_the_canonical_reference():
    """Found in production 2026-07-28: the header showed the chapter TITLE while
    the source chip showed the chapter NUMBER, so a reader who asked for
    citations got two different-looking references to the same passage."""
    from src.rag.prompt import build_messages

    chunks = [
        {
            "content": "texto",
            "metadata": {
                "book": "A Gênese",
                "chapter": "CAPÍTULO XIV",
                "chapter_title": "OS FLUIDOS",
                "item_number": "18",
            },
        }
    ]
    system, _ = build_messages("q", chunks, [])
    header = next(l for l in system.splitlines() if l.startswith("[1]"))

    assert "CAPÍTULO XIV" in header
    assert "OS FLUIDOS" in header
    assert "18" in header


def test_the_header_survives_a_chunk_with_no_chapter_reference():
    from src.rag.prompt import build_messages

    chunks = [
        {
            "content": "texto",
            "metadata": {
                "book": "O Livro dos Espíritos",
                "chapter_title": "Da Encarnação",
                "item_number": "132",
            },
        }
    ]
    system, _ = build_messages("q", chunks, [])
    header = next(l for l in system.splitlines() if l.startswith("[1]"))
    assert "Da Encarnação" in header


def test_the_prompt_forbids_the_model_talking_about_itself():
    """Production 2026-07-28: 'Sim, posso fornecer citações... é importante
    notar que as citações devem ser usadas para...'"""
    from src.rag.prompt import build_messages

    system, _ = build_messages("q", [], [])
    assert "Nunca fale de si mesmo" in system
