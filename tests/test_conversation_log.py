"""The anonymous turn log.

Its whole reason to exist is being *unable* to reconstruct one person's session,
so the tests here are mostly about what must NOT appear. A field added later
without thinking is the realistic failure — hence the sweep over the whole
payload instead of assertions field by field.
"""

import json
import uuid

import pytest

from src.rag import conversation_log
from src.rag.conversation_log import log_chat_turn


def _capture(stream, question, result, **kw):
    conversation_log.log_chat_turn(question, result, latency_ms=10, **kw)
    line = stream.getvalue().strip()
    return json.loads(line), line


NORMAL = {
    "answer": "Kardec escreve que o perispírito é o envoltório fluídico.",
    "sources": [
        {"book": "A Gênese", "chapter_title": "OS FLUIDOS", "item_number": "22"}
    ],
    "suggested_questions": ["e o corpo?", "e a alma?"],
    "not_found": False,
    "safety_level": "normal",
}


def test_normal_turn_is_one_valid_json_line_with_no_logging_prefix(stream):
    payload, line = _capture(stream, "o que é o perispírito?", NORMAL)
    assert line.startswith("{") and line.endswith(
        "}"
    ), "prefixo de logging quebra o parsing"
    assert payload["event"] == "chat_turn"
    assert payload["question"] == "o que é o perispírito?"
    assert payload["n_sources"] == 1
    assert payload["sources"][0]["chapter"] == "OS FLUIDOS"
    assert payload["n_chips"] == 2
    assert payload["latency_ms"] == 10


@pytest.mark.parametrize("level", ["crise", "abalo"])
def test_sensitive_levels_record_no_text_at_all(stream, level):
    """Health data. The level is recorded; not one word the person wrote."""
    result = dict(NORMAL, safety_level=level, answer="qualquer coisa que ela escreveu")
    payload, line = _capture(stream, "estou sofrendo muito e queria sumir", result)

    assert payload["safety_level"] == level
    assert "question" not in payload, "ausente, não vazio"
    assert "answer" not in payload
    assert "sofrendo" not in line and "sumir" not in line


def test_direct_identifiers_are_scrubbed(stream):
    question = (
        "meu email é maria.silva@gmail.com, meu cpf 123.456.789-00, "
        "telefone (11) 98765-4321 e cep 01310-100"
    )
    payload, line = _capture(stream, question, NORMAL)

    assert "maria.silva@gmail.com" not in line
    assert "123.456.789-00" not in line
    assert "98765-4321" not in line
    assert "01310-100" not in line
    assert "[email]" in payload["question"] and "[cpf]" in payload["question"]


def test_without_consent_nothing_could_rebuild_a_session(stream):
    """The 2026-07-27 guarantee, now explicitly scoped to the default regime.

    Without consent the record stays what it was: loose turns with nothing
    stitching them together. The sibling test below guards the other side —
    that the link exists ONLY when the header arrived.

    Swept over the whole payload, not field by field: the realistic failure is
    someone adding a field later without thinking about linkage.
    """
    payload, line = _capture(stream, "o que é a prece?", NORMAL, suggested_mode=None)

    # Token by token, not substring: "n_chips" contains "ip", and a naive `in`
    # check flags a field that is perfectly fine.
    forbidden = {
        "session",
        "conversation",
        "user",
        "ip",
        "addr",
        "history",
        "cookie",
        "agent",
    }
    # Counts are exempt, and only counts. `n_history` records how many previous
    # turns the client sent, never one word of them — rule nº2 of 2026-07-27 is
    # about the content, and a number cannot rebuild a conversation. The
    # exemption is spelled out here rather than removed from `forbidden` so
    # that a future `history` or `history_text` still trips the sweep.
    counts_only = {"n_history"}
    offending = [
        k
        for k in payload
        if k not in counts_only
        and forbidden & set(k.lower().replace("-", "_").split("_"))
    ]
    assert offending == []
    assert "192.168" not in line and "x-forwarded" not in line.lower()


def test_turn_id_is_always_present_and_returned(stream):
    returned = log_chat_turn("o que é o perispírito?", NORMAL, latency_ms=10)
    payload = json.loads(stream.getvalue().strip())
    assert payload["turn_id"] == returned
    uuid.UUID(payload["turn_id"])  # levanta se não for um UUID válido


def test_session_id_absent_without_consent(stream):
    payload, _ = _capture(stream, "o que é o perispírito?", NORMAL)
    assert "session_id" not in payload


def test_session_id_present_when_given(stream):
    payload, _ = _capture(
        stream, "o que é o perispírito?", NORMAL, session_id="abc-123"
    )
    assert payload["session_id"] == "abc-123"


def test_session_id_absent_not_null_when_empty_string(stream):
    """Um header vazio é recusa, não uma sessão chamada ""."""
    payload, _ = _capture(stream, "pergunta", NORMAL, session_id="")
    assert "session_id" not in payload


def test_crisis_keeps_session_but_never_text(stream):
    """Consent does not unlock crisis text. It never does, in any regime."""
    result = dict(NORMAL, safety_level="crise", answer="o que ela escreveu")
    payload, line = _capture(stream, "quero morrer", result, session_id="abc-123")

    assert payload["session_id"] == "abc-123"
    assert payload["safety_level"] == "crise"
    assert "question" not in payload
    assert "answer" not in payload
    assert "morrer" not in line


def test_logging_never_breaks_a_good_answer(stream):
    """Observability must not be able to fail a request that already worked."""
    conversation_log.log_chat_turn("pergunta", {"sources": "não é lista"}, latency_ms=1)
    # não levantou; o erro foi registrado em outro logger
