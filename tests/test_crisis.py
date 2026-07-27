"""The deterministic crisis floor, extracted from reflect_prompt.py when the
Refletir mode was switched off (see
docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md).

These tests guard /chat, not Refletir: the fixed exit and the CVV note are the
guaranteed floor under every answer the product still ships.
"""

from src.rag.crisis import (
    CRISIS_EXIT_MESSAGE,
    CRISIS_NOTE,
    mentions_suicide_topic,
    needs_crisis_note,
    needs_medical_caveat,
)


def test_needs_medical_caveat_true_for_vozes():
    assert needs_medical_caveat("escuto vozes à noite") is True


def test_needs_medical_caveat_true_for_sombras():
    assert needs_medical_caveat("estou vendo sombras") is True


def test_needs_medical_caveat_false_for_normal_situation():
    assert needs_medical_caveat("meu pai faleceu") is False


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


def test_needs_crisis_note_false_for_doctrinal_suicide_question():
    # Topic-level mention, no first-person ideation: must NOT take the fixed
    # exit — the app must be able to teach what the works say about suicide.
    assert needs_crisis_note("O que Kardec diz sobre o suicídio?") is False
    assert needs_crisis_note("o que acontece com quem comete suicidio?") is False


def test_crisis_exit_message_has_support_lines():
    assert "188" in CRISIS_EXIT_MESSAGE  # CVV
    assert "192" in CRISIS_EXIT_MESSAGE  # SAMU
    assert "não está só" in CRISIS_EXIT_MESSAGE


def test_needs_crisis_note_true_for_first_person_ideation_with_topic_word():
    assert needs_crisis_note("penso em suicídio") is True
    assert needs_crisis_note("estou pensando em me suicidar") is True
    assert needs_crisis_note("quero me suicidar") is True


def test_mentions_suicide_topic_true_for_doctrinal_question():
    assert mentions_suicide_topic("O que Kardec diz sobre o suicídio?") is True
    assert mentions_suicide_topic("o que acontece apos o suicidio") is True


def test_mentions_suicide_topic_false_without_the_topic():
    assert mentions_suicide_topic("estou triste com meu trabalho") is False
    assert mentions_suicide_topic("o que Kardec diz sobre a morte?") is False
