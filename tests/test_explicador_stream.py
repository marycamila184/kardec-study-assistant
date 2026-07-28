"""explicar_stream: the same study answer as explicar(), delivered as it arrives.

Explicador answers with structured JSON, so the guarantee under test is that
the reader sees the explanation being written and never the JSON around it —
and that `done` still matches what POST /study would have returned.

See docs/superpowers/specs/2026-07-28-study-trecho-streaming-design.md
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.rag.explicador import build_chapter_context, explicar_stream, prepare_study

EVANGELHO = "O Evangelho Segundo o Espiritismo"

_CHUNK = {
    "content": "132. A encarnação tem por fim fazê-los progredir.",
    "footnote_context": "",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação",
        "item_number": "132",
    },
    "distance": 0.0,
}

_CONTEXTO = (
    "Kardec responde que a encarnação existe para o progresso do espírito. "
    "A palavra “provação” aparece adiante no mesmo capítulo."
)
_PAYLOAD = json.dumps(
    {
        "contexto": _CONTEXTO,
        "conceitos_chave": ["encarnação", "progresso"],
        "perguntas": ["Por que o espírito progride encarnado?"],
    }
)


def _fake_stream_chunks(raw: str, size: int):
    """The provider's deltas: arbitrary slices, plus the empty keep-alive and
    the final choice-less chunk that delta_text() exists to absorb."""
    for i in range(0, len(raw), size):
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content=raw[i : i + size]))])
    yield MagicMock(choices=[])


@pytest.fixture
def _ctx():
    with (
        patch("src.rag.explicador.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.chapter_commentary", return_value=[]),
    ):
        return prepare_study("O Livro dos Espíritos", "132")


def _run(ctx, raw=_PAYLOAD, size=9):
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_stream_chunks(raw, size)
    with (
        patch("src.rag.explicador.get_client", return_value=client),
        patch("src.rag.explicador.curar", return_value=[]),
    ):
        events = list(explicar_stream(ctx))
    tokens = [p for kind, p in events if kind == "token"]
    done = [p for kind, p in events if kind == "done"]
    return tokens, done


def test_prepare_study_returns_none_for_a_missing_item():
    with patch("src.rag.explicador.retrieve_by_item", return_value=[]):
        assert prepare_study("O Livro dos Espíritos", "99999") is None


def test_tokens_rebuild_the_contexto(_ctx):
    tokens, _ = _run(_ctx)
    assert "".join(tokens) == _CONTEXTO


def test_no_token_ever_contains_json_syntax(_ctx):
    """The reader must never see the braces the explanation arrived in."""
    tokens, _ = _run(_ctx, size=3)
    joined = "".join(tokens)
    for leak in ('"contexto"', "conceitos_chave", "{", "}", "\\u"):
        assert leak not in joined


def test_done_carries_the_whole_body(_ctx):
    _, done = _run(_ctx)
    assert len(done) == 1
    body = done[0]
    assert body["contexto"] == _CONTEXTO
    assert body["conceitos_chave"] == ["encarnação", "progresso"]
    assert body["perguntas"] == ["Por que o espírito progride encarnado?"]
    assert body["original_text"] == _CHUNK["content"]
    assert body["sources"][0]["item_number"] == "132"
    assert body["generation_failed"] is False


@pytest.mark.parametrize("size", [1, 2, 5, 17, 500])
def test_done_is_identical_whatever_the_chunk_size(_ctx, size):
    _, done = _run(_ctx, size=size)
    assert done[0]["contexto"] == _CONTEXTO


def test_accent_escaped_payload_still_reads_as_portuguese(_ctx):
    """ensure_ascii=True is what several providers send."""
    raw = json.dumps(
        {"contexto": _CONTEXTO, "conceitos_chave": [], "perguntas": []},
        ensure_ascii=True,
    )
    tokens, done = _run(_ctx, raw=raw, size=4)
    assert "".join(tokens) == _CONTEXTO
    assert done[0]["contexto"] == _CONTEXTO


def test_unusable_response_is_generation_failed_not_an_exception(_ctx):
    tokens, done = _run(_ctx, raw="isto não é json", size=6)
    assert tokens == []
    assert done[0]["generation_failed"] is True
    assert done[0]["contexto"] == ""


def test_a_failure_mid_stream_does_not_leave_partial_text_as_the_answer(_ctx):
    """Tokens may already be on screen; `done` is what stands as the answer."""

    def _explode(*args, **kwargs):
        yield MagicMock(
            choices=[MagicMock(delta=MagicMock(content='{"contexto": "come'))]
        )
        raise RuntimeError("provider dropped the connection")

    client = MagicMock()
    client.chat.completions.create.return_value = _explode()
    with (
        patch("src.rag.explicador.get_client", return_value=client),
        patch("src.rag.explicador.curar", return_value=[]),
    ):
        events = list(explicar_stream(_ctx))

    done = [p for kind, p in events if kind == "done"][0]
    assert done["generation_failed"] is True
    assert done["contexto"] == ""


def test_related_items_come_from_curador(_ctx):
    related = [{"book": "O Livro dos Espíritos", "item_number": "133", "chapter": "IV"}]
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_stream_chunks(_PAYLOAD, 20)
    with (
        patch("src.rag.explicador.get_client", return_value=client),
        patch("src.rag.explicador.curar", return_value=related),
    ):
        events = list(explicar_stream(_ctx))
    done = [p for kind, p in events if kind == "done"][0]
    assert done["related_items"] == related


def test_chapter_context_exposes_the_grounding_items():
    """The explanation cites the chapter's other items, so they must be
    openable — grouped per item, subchunks rejoined in order."""
    ctx = {
        "commentary": [
            {
                "content": "2. O incrédulo sorri a esta parábola,",
                "metadata": {
                    "book": EVANGELHO,
                    "chapter_title": "MUITOS OS CHAMADOS",
                    "item_number": "2",
                },
            },
            {
                "content": "que lhe parece de pueril ingenuidade.",
                "metadata": {
                    "book": EVANGELHO,
                    "chapter_title": "MUITOS OS CHAMADOS",
                    "item_number": "2",
                },
            },
            {
                "content": "5. Larga é a porta da perdição.",
                "metadata": {
                    "book": EVANGELHO,
                    "chapter_title": "MUITOS OS CHAMADOS",
                    "item_number": "5",
                },
            },
        ]
    }
    out = build_chapter_context(ctx)

    assert [c["item_number"] for c in out] == ["2", "5"]
    assert out[0]["excerpt"] == (
        "2. O incrédulo sorri a esta parábola, que lhe parece de pueril ingenuidade."
    )
    assert out[0]["chapter_title"] == "MUITOS OS CHAMADOS"


def test_chapter_context_drops_section_placeholders():
    """'section-N' is the parser's marker for an unnumbered heading — not an
    item anyone can look up."""
    ctx = {
        "commentary": [
            {
                "content": "Instruções dos Espíritos",
                "metadata": {"book": EVANGELHO, "item_number": "section-3"},
            },
            {
                "content": "12. Principalmente ao ensino dos Espíritos.",
                "metadata": {"book": EVANGELHO, "item_number": "12"},
            },
        ]
    }
    assert [c["item_number"] for c in build_chapter_context(ctx)] == ["12"]


def test_chapter_context_is_empty_without_commentary():
    assert build_chapter_context({}) == []
    assert build_chapter_context({"commentary": []}) == []
