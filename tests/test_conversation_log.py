"""The anonymous turn log.

Its whole reason to exist is being *unable* to reconstruct one person's session,
so the tests here are mostly about what must NOT appear. A field added later
without thinking is the realistic failure — hence the sweep over the whole
payload instead of assertions field by field.
"""

import io
import json

import pytest

from src.rag import conversation_log


@pytest.fixture
def stream(monkeypatch):
    """Points the handler at a buffer.

    Neither capsys nor capfd sees these lines: the handler binds `sys.stdout` at
    import time, so it keeps writing to whatever object existed then. Swapping
    the handler's own stream is precise and leaves production code alone.
    """
    buffer = io.StringIO()
    monkeypatch.setattr(conversation_log._logger.handlers[0], "stream", buffer)
    return buffer


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


def test_nothing_that_could_rebuild_a_session_is_logged(stream):
    """Swept over the whole payload, not field by field: the realistic failure
    is someone adding a field later without thinking about linkage."""
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
    offending = [
        k for k in payload if forbidden & set(k.lower().replace("-", "_").split("_"))
    ]
    assert offending == []
    assert "192.168" not in line and "x-forwarded" not in line.lower()


def test_logging_never_breaks_a_good_answer(stream):
    """Observability must not be able to fail a request that already worked."""
    conversation_log.log_chat_turn("pergunta", {"sources": "não é lista"}, latency_ms=1)
    # não levantou; o erro foi registrado em outro logger
