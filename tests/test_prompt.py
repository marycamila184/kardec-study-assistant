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
    assert "sem pergunta de encerramento" in system


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
    assert "abalo emocional" in system
    assert "acolher vem primeiro" in system


def test_the_abalo_text_declares_precedence_over_the_voice_rule():
    """It tells the model to acknowledge feeling BEFORE doctrine, while the
    voice rule says to start on substance. Left implicit, that contradiction
    gets resolved unpredictably — measured on 2026-07-28, when a rule
    contradicting an earlier one produced no effect at all."""
    system, _ = build_messages("estou mal", [_PROMPT_CHUNK], [], sensitive=True)
    assert "exceção à regra de começar pela substância" in system


def test_build_messages_not_sensitive_omits_gentle_instruction():
    system, _ = build_messages("o que é X?", [_PROMPT_CHUNK], [], sensitive=False)
    assert "abalo emocional" not in system


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


def test_the_prompt_forbids_announcing_but_allows_correcting():
    """Announcing configuration is what grates ('sim, posso fornecer
    citações...'). Apologising for a wrong answer is honesty, and the reader
    asked for it to stay."""
    from src.rag.prompt import build_messages

    system, _ = build_messages("q", [], [])
    assert "sem preâmbulo" in system
    assert "Corrigir-se é diferente" in system


def test_absent_terms_reach_the_model_when_there_are_any():
    from src.rag.prompt import build_messages

    plain, _ = build_messages("q", [], [])
    assert "AVISO:" not in plain

    warned, _ = build_messages("q", [], [], absent_terms=["pineal"])
    assert '"pineal" não aparece' in warned
    assert "Não trate esse termo como doutrina" in warned


def test_the_near_miss_rule_states_its_exception():
    """A 'did you mean this?' is the one place the answer may end on a question.
    Left implicit it would contradict the rule that follow-ups live in [SEGUIR],
    and a rule contradicting its neighbour gets obeyed unpredictably — measured
    on 2026-07-28, when citation_precision produced nothing at all for exactly
    that reason."""
    from src.rag.prompt import build_messages

    system, _ = build_messages("q", [], [])
    assert "não encontrou exatamente aquilo" in system
    assert "único caso em que a resposta pode terminar com uma pergunta" in system
    assert "sem pergunta de encerramento" in system


def test_the_prompts_come_from_their_files_and_ship_with_the_package():
    """They live as Markdown so they can be refined without going through
    Python string escaping. A missing file must raise rather than silently
    remove a rule and leave everything running."""
    import pathlib

    import pytest

    from src.rag.prompt_files import _DIR, load

    assert (_DIR / "chat-system.md").exists()
    assert load("chat-system").startswith("# Quem você é")

    with pytest.raises(FileNotFoundError):
        load("this-prompt-does-not-exist")

    # Every file is reachable by the name the code uses.
    for path in _DIR.glob("*.md"):
        if path.stem != "README":
            assert load(path.stem)
