"""POST /study/stream — the Server-Sent Events lane for Estudar uma Obra.

POST /study is untouched and keeps its contract; these tests cover the new
route only. What they guard is that a missing item is still an HTTP 404 rather
than a successful empty stream, and that `done` carries the full study body.

See docs/superpowers/specs/2026-07-28-study-trecho-streaming-design.md
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_CTX = {
    "chunks": [
        {
            "metadata": {
                "book": "O Livro dos Espíritos",
                "chapter_title": "Da Encarnação",
                "item_number": "132",
            }
        }
    ],
    "original_text": "132. A encarnação tem por fim fazê-los progredir.",
    "related": [],
    "system": "sistema",
    "messages": [{"role": "user", "content": "item"}],
}

_BODY = {
    "original_text": _CTX["original_text"],
    "contexto": "Kardec responde que a encarnação existe para o progresso.",
    "conceitos_chave": ["encarnação"],
    "perguntas": ["Por que o espírito progride encarnado?"],
    "related_items": [],
    "sources": [
        {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        }
    ],
    "chapter_context": [
        {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter_title": "Da Encarnação",
            "item_number": "133",
            "excerpt": "133. O comentário do capítulo.",
        }
    ],
    "generation_failed": False,
}


def _parse_sse(body: str) -> list[tuple[str, dict]]:
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


def _fake_stream(ctx):
    yield "token", "Kardec responde que "
    yield "token", "a encarnação existe para o progresso."
    yield "done", _BODY


def _request():
    payload = {"book": "O Livro dos Espíritos", "item_number": "132"}
    return client.post("/study/stream", json=payload)


def test_missing_item_is_a_404_not_an_empty_stream():
    with patch("src.api.routes.prepare_study", return_value=None):
        response = client.post(
            "/study/stream",
            json={"book": "O Livro dos Espíritos", "item_number": "99999"},
        )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "item_not_found"


def test_source_then_tokens_then_done():
    with (
        patch("src.api.routes.prepare_study", return_value=_CTX),
        patch("src.api.routes.explicar_stream", _fake_stream),
    ):
        response = _request()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)

    assert [name for name, _ in events] == ["source", "token", "token", "done"]
    tokens = "".join(payload["text"] for name, payload in events if name == "token")
    assert tokens == "Kardec responde que a encarnação existe para o progresso."


def test_the_passage_arrives_before_the_first_token():
    """Otherwise the explanation appears on screen above the text it explains."""
    with (
        patch("src.api.routes.prepare_study", return_value=_CTX),
        patch("src.api.routes.explicar_stream", _fake_stream),
    ):
        events = _parse_sse(_request().text)

    name, payload = events[0]
    assert name == "source"
    assert payload["original_text"] == _CTX["original_text"]
    assert payload["sources"][0]["item_number"] == "132"
    assert payload["sources"][0]["chapter_title"] == "Da Encarnação"


def test_done_matches_the_study_response_shape():
    with (
        patch("src.api.routes.prepare_study", return_value=_CTX),
        patch("src.api.routes.explicar_stream", _fake_stream),
    ):
        events = _parse_sse(_request().text)

    done = [payload for name, payload in events if name == "done"][0]
    assert set(done) == set(_BODY)
    assert done["contexto"] == _BODY["contexto"]
    assert done["sources"][0]["item_number"] == "132"
    assert done["generation_failed"] is False


def test_accented_text_is_not_escaped_on_the_wire():
    """ensure_ascii=False keeps the Portuguese readable in the SSE frames."""
    with (
        patch("src.api.routes.prepare_study", return_value=_CTX),
        patch("src.api.routes.explicar_stream", _fake_stream),
    ):
        raw = _request().text
    assert "encarnação" in raw
