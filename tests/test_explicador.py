import json
import logging
from unittest.mock import MagicMock, patch

from src.rag.explicador import explicar

_CHUNK_WITH_FOOTNOTE = {
    "content": "1. Que é Deus?",
    "footnote_context": "[Nota 1] Explicação editorial de exemplo.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Noções Preliminares",
        "item_number": "1",
    },
    "distance": 0.0,
}

_MULTI_CHUNK_A = {
    "content": "Primeiro subtrecho, curto e específico.",
    "footnote_context": "",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação",
        "item_number": "132",
    },
    "distance": 0.0,
}
_MULTI_CHUNK_B = {
    "content": "Segundo subtrecho, com outro assunto diluidor.",
    "footnote_context": "",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação",
        "item_number": "132",
    },
    "distance": 0.0,
}


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_explicar_returns_none_when_no_chunks():
    with patch("src.rag.explicador.retrieve_by_item", return_value=[]):
        result = explicar("O Livro dos Espíritos", "1")
    assert result is None


def test_explicar_passes_footnote_context_to_prompt():
    llm_json = '{"contexto": "Contexto de teste.", "conceitos_chave": []}'
    with (
        patch("src.rag.explicador.settings.prose_provider", "ollama"),
        patch(
            "src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]
        ),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador.build_explicador_messages") as mock_build,
        patch("src.rag.explicador.get_client") as mock_client,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json)
        )
        explicar("O Livro dos Espíritos", "1")
    assert (
        mock_build.call_args.kwargs["footnote_context"]
        == "[Nota 1] Explicação editorial de exemplo."
    )


def test_explicar_returns_contexto_from_llm():
    llm_json = '{"contexto": "Contexto de teste.", "conceitos_chave": []}'
    with (
        patch("src.rag.explicador.settings.prose_provider", "ollama"),
        patch(
            "src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]
        ),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json)
        )
        result = explicar("O Livro dos Espíritos", "1")
    assert result["contexto"] == "Contexto de teste."
    assert result["original_text"] == "1. Que é Deus?"


def test_explicar_degrades_gracefully_when_related_retrieval_fails():
    llm_json = '{"contexto": "Contexto de teste.", "conceitos_chave": []}'

    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    with (
        patch("src.rag.explicador.settings.prose_provider", "ollama"),
        patch(
            "src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]
        ),
        patch("src.rag.explicador.retrieve", side_effect=_raise),
        patch("src.rag.explicador.curar", return_value=[]) as mock_curar,
        patch("src.rag.explicador.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json)
        )
        result = explicar("O Livro dos Espíritos", "1")
    assert result is not None
    assert result["contexto"] == "Contexto de teste."
    assert result["related_items"] == []
    mock_curar.assert_called_once_with("1. Que é Deus?", [])


def test_explicar_retrieves_related_using_first_subchunk_only():
    llm_json = '{"contexto": "c", "conceitos_chave": []}'
    with (
        patch("src.rag.explicador.settings.prose_provider", "ollama"),
        patch(
            "src.rag.explicador.retrieve_by_item",
            return_value=[_MULTI_CHUNK_A, _MULTI_CHUNK_B],
        ),
        patch("src.rag.explicador.retrieve", return_value=[]) as mock_retrieve,
        patch("src.rag.explicador.curar", return_value=[]) as mock_curar,
        patch("src.rag.explicador.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json)
        )
        explicar("O Livro dos Espíritos", "132")
    # related retrieval uses ONLY the first subchunk
    assert mock_retrieve.call_args[0][0] == "Primeiro subtrecho, curto e específico."
    # curar still receives the FULL concatenated original text
    full_text = (
        "Primeiro subtrecho, curto e específico.\n\n"
        "Segundo subtrecho, com outro assunto diluidor."
    )
    assert mock_curar.call_args[0][0] == full_text


def test_explicar_logs_on_llm_error(caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("API error")

    with (
        patch(
            "src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]
        ),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador.get_client") as mock_client,
        caplog.at_level(logging.ERROR, logger="src.rag.explicador"),
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError(
            "API error"
        )
        explicar("O Livro dos Espíritos", "1")
    assert any("explicador" in r.message.lower() for r in caplog.records)


def test_explicar_passes_chapter_commentary_to_prompt(monkeypatch):
    ev_chunk = {
        "content": "1. O reino dos céus é semelhante a um pai de família...",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter": "CAPÍTULO XX",
            "chapter_title": "OS TRABALHADORES DA ÚLTIMA HORA",
            "item_number": "1",
        },
        "footnote_context": "",
    }
    captured = {}

    def _capture_build(
        main_text,
        related,
        footnote_context="",
        chapter_commentary_chunks=None,
        markers=False,
        **kw,
    ):
        captured["commentary"] = chapter_commentary_chunks
        return "SYS", [{"role": "user", "content": "x"}]

    monkeypatch.setattr("src.rag.explicador.settings.prose_provider", "ollama")
    monkeypatch.setattr(
        "src.rag.explicador.retrieve_by_item", lambda b, i, c=None: [ev_chunk]
    )
    monkeypatch.setattr("src.rag.explicador.retrieve", lambda q, top_k=6: [])
    monkeypatch.setattr("src.rag.explicador.curar", lambda t, r: [])
    monkeypatch.setattr(
        "src.rag.explicador.chapter_commentary",
        lambda b, c, ex: [{"content": "comentario kardec", "metadata": {}}],
    )
    monkeypatch.setattr("src.rag.explicador.build_explicador_messages", _capture_build)

    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(content='{"contexto": "c", "conceitos_chave": []}')
            )
        ]
    )
    monkeypatch.setattr("src.rag.explicador.get_client", lambda role="json": client)

    explicar("O Evangelho Segundo o Espiritismo", "1", "CAPÍTULO XX")
    assert captured["commentary"] == [{"content": "comentario kardec", "metadata": {}}]


def test_explicar_no_commentary_for_non_evangelho(monkeypatch):
    le_chunk = {
        "content": "132. A encarnação...",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter": "CAP I",
            "item_number": "132",
        },
        "footnote_context": "",
    }

    captured = {}

    def _capture_build(
        main_text,
        related,
        footnote_context="",
        chapter_commentary_chunks=None,
        markers=False,
        **kw,
    ):
        captured["commentary"] = chapter_commentary_chunks
        return "SYS", [{"role": "user", "content": "x"}]

    monkeypatch.setattr("src.rag.explicador.settings.prose_provider", "ollama")
    monkeypatch.setattr(
        "src.rag.explicador.retrieve_by_item", lambda b, i, c=None: [le_chunk]
    )
    monkeypatch.setattr("src.rag.explicador.retrieve", lambda q, top_k=6: [])
    monkeypatch.setattr("src.rag.explicador.curar", lambda t, r: [])
    monkeypatch.setattr(
        "src.rag.explicador.chapter_commentary",
        lambda b, c, ex: [],  # Returns [] for non-Evangelho due to self-gating
    )
    monkeypatch.setattr("src.rag.explicador.build_explicador_messages", _capture_build)
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(content='{"contexto": "c", "conceitos_chave": []}')
            )
        ]
    )
    monkeypatch.setattr("src.rag.explicador.get_client", lambda role="json": client)

    explicar("O Livro dos Espíritos", "132", "CAP I")
    assert captured["commentary"] == []


# --- lane pinning ---------------------------------------------------------
#
# Explicador is pinned to the JSON lane. These tests exist because the pin is a
# product decision, not an implementation detail: PROSE_PROVIDER is one switch
# for the whole app, and before the pin, enabling the prose lane for /chat
# silently moved /study onto riv-ai-v2 — which failed the marker contract on
# 2/3 study items and misattributed a passage's own work. If someone reconnects
# /study to that switch, these fail.


def _stub_retrieval(monkeypatch, exp):
    monkeypatch.setattr(
        exp,
        "retrieve_by_item",
        lambda *a, **k: [
            {
                "metadata": {
                    "book": "O Livro dos Espíritos",
                    "item_number": "625",
                    "chapter_title": "Cap",
                },
                "content": "trecho principal",
                "footnote_context": "",
            }
        ],
    )
    monkeypatch.setattr(exp, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(exp, "chapter_commentary", lambda *a, **k: [])
    monkeypatch.setattr(exp, "curar", lambda *a, **k: [])


def _json_client(payload):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=payload))
    ]
    return client


_PAYLOAD = json.dumps(
    {"contexto": "Contexto via JSON.", "conceitos_chave": ["dever: obrigação"]}
)


def test_explicador_stays_on_the_json_lane_when_the_prose_lane_is_enabled(monkeypatch):
    """The pin: PROSE_PROVIDER must not reach /study."""
    import src.rag.explicador as exp

    monkeypatch.setattr(exp.settings, "prose_provider", "ollama")
    _stub_retrieval(monkeypatch, exp)
    client = _json_client(_PAYLOAD)
    seen = {}

    def fake_get_client(role="json"):
        seen["role"] = role
        return client

    monkeypatch.setattr(exp, "get_client", fake_get_client)

    out = exp.explicar("O Livro dos Espíritos", "625")

    assert seen["role"] == "json"
    assert out["contexto"] == "Contexto via JSON."
    assert out["generation_failed"] is False


def test_explicador_always_sends_the_json_template(monkeypatch):
    """Format follows the lane, and the lane is fixed — so the marker template
    must never be sent, whatever PROSE_PROVIDER says."""
    import src.rag.explicador as exp

    monkeypatch.setattr(exp.settings, "prose_provider", "ollama")
    _stub_retrieval(monkeypatch, exp)
    client = _json_client(_PAYLOAD)
    monkeypatch.setattr(exp, "get_client", lambda role="json": client)

    exp.explicar("O Livro dos Espíritos", "625")

    system = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "REGRA ABSOLUTA DE FORMATO" not in system  # the marker header
    assert '"conceitos_chave"' in system


def test_explicador_never_calls_the_prose_lane(monkeypatch):
    """prose_completion is no longer on the /study path at all."""
    import src.rag.explicador as exp

    monkeypatch.setattr(exp.settings, "prose_provider", "ollama")
    _stub_retrieval(monkeypatch, exp)
    monkeypatch.setattr(exp, "get_client", lambda role="json": _json_client(_PAYLOAD))

    called = []
    monkeypatch.setattr(
        "src.rag.prose.prose_completion",
        lambda *a, **k: called.append(1) or "",
    )

    exp.explicar("O Livro dos Espíritos", "625")

    assert called == []


def test_explicador_marks_failure_on_unparseable_output(monkeypatch):
    import src.rag.explicador as exp

    monkeypatch.setattr(exp.settings, "prose_provider", "ollama")
    monkeypatch.setattr(
        exp,
        "retrieve_by_item",
        lambda *a, **k: [
            {
                "metadata": {
                    "book": "O Livro dos Espíritos",
                    "item_number": "625",
                    "chapter_title": "Cap",
                },
                "content": "trecho",
                "footnote_context": "",
            }
        ],
    )
    monkeypatch.setattr(exp, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(exp, "chapter_commentary", lambda *a, **k: [])
    monkeypatch.setattr(exp, "curar", lambda *a, **k: [])
    # Unparseable output must surface as generation_failed, with no network
    # rescue: /study has no second lane to fall back to since the pin.
    monkeypatch.setattr(exp, "get_client", lambda role="json": _json_client("lixo"))

    out = exp.explicar("O Livro dos Espíritos", "625")
    assert out["generation_failed"] is True
    assert out["contexto"] == ""
