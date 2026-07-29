"""POST /chat/stream — the Server-Sent Events lane.

POST /chat is untouched and keeps its contract; these tests cover the new route
only. What they guard is that everything decided in code — the crisis exit, the
size cap — still answers before a stream is ever opened.

See docs/superpowers/specs/2026-07-27-streaming-design.md
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Turns a raw SSE body into [(event_name, payload), ...]."""
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((name, data))
    return events


def _stream(question: str, **kwargs):
    payload = {"question": question, "history": [], **kwargs}
    response = client.post("/chat/stream", json=payload)
    return response, _parse_sse(response.text)


_STREAM_EVENTS = [
    ("token", "Kardec escreve "),
    ("token", "que o espírito sobrevive."),
]

_DONE_RESULT = {
    "answer": "Kardec escreve que o espírito sobrevive.",
    "sources": [
        {
            "book": "O Livro dos Espíritos",
            "chapter": "Da Encarnação",
            "chapter_ref": None,
            "item_number": "132",
            "excerpt": "A encarnação tem por fim fazê-los progredir.",
        }
    ],
    "suggested_questions": ["E o perispírito?"],
    "not_found": False,
    "generation_failed": False,
    "safety_level": "normal",
}


def _fake_generate_stream(*args, **kwargs):
    yield from _STREAM_EVENTS
    yield "done", _DONE_RESULT


def test_stream_route_sets_the_headers_that_keep_proxies_from_buffering():
    with (
        patch("src.api.routes.generate_stream", _fake_generate_stream),
        patch("src.api.routes.classify_intent", return_value={"mode": None}),
    ):
        response, _ = _stream("o que acontece após a morte?")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"


def test_tokens_arrive_then_exactly_one_done():
    with (
        patch("src.api.routes.generate_stream", _fake_generate_stream),
        patch("src.api.routes.classify_intent", return_value={"mode": None}),
    ):
        _, events = _stream("o que acontece após a morte?")

    assert [name for name, _ in events] == ["token", "token", "done"]
    assert events[0][1]["text"] == "Kardec escreve "


def test_done_payload_carries_the_full_chat_response_shape():
    with (
        patch("src.api.routes.generate_stream", _fake_generate_stream),
        patch("src.api.routes.classify_intent", return_value={"mode": "estudar_obra"}),
    ):
        _, events = _stream("me explica a questão 132")

    done = events[-1][1]
    assert done["answer"] == _DONE_RESULT["answer"]
    assert done["sources"][0]["book"] == "O Livro dos Espíritos"
    assert done["suggested_questions"] == ["E o perispírito?"]
    assert done["safety_level"] == "normal"
    assert done["suggested_mode"] == "estudar_obra"
    assert done["suggested_item_number"] == "132"


def test_suicidal_ideation_emits_no_token_event():
    """The guaranteed floor: the crisis exit is decided in code and arrives
    whole, never streamed."""
    _, events = _stream("não aguento mais, quero me matar")

    assert [name for name, _ in events] == ["done"]
    assert events[0][1]["safety_level"] == "crise"
    assert "188" in events[0][1]["answer"]


def test_an_oversized_message_never_opens_a_stream():
    from src.api.limits import TOO_LONG_MESSAGE

    def _boom(*args, **kwargs):
        raise AssertionError("the size cap must answer before generation")

    with patch("src.api.routes.generate_stream", _boom):
        _, events = _stream("palavra " * 2500)

    assert [name for name, _ in events] == ["done"]
    assert events[0][1]["answer"] == TOO_LONG_MESSAGE


def test_the_turn_is_logged_once_with_the_final_answer():
    with (
        patch("src.api.routes.generate_stream", _fake_generate_stream),
        patch("src.api.routes.classify_intent", return_value={"mode": None}),
        # A string, não o MagicMock padrão: log_chat_turn devolve o turn_id que
        # vai para o corpo tipado da resposta desde 2026-07-28.
        patch("src.api.routes.log_chat_turn", return_value="turn-1") as mock_log,
    ):
        _stream("o que acontece após a morte?")

    assert mock_log.call_count == 1
    assert mock_log.call_args[0][1]["answer"] == _DONE_RESULT["answer"]
