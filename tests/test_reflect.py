import logging
from unittest.mock import MagicMock, patch

import pytest

from src.rag.reflect import reflect

_CHUNK_1 = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "150",
        "chapter_title": "Da Alma",
    },
    "distance": 0.3,
}
_CHUNK_2 = {
    "content": "A angústia é uma prova da alma.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "132",
        "chapter_title": "Da Encarnação",
    },
    "distance": 0.5,
}
_CHUNK_3 = {
    "content": "O amor é a lei suprema.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "item_number": "section-1",
        "chapter_title": "",
    },
    "distance": 0.7,
}

_LLM_JSON = '{"opening": "Compreendemos sua dor.", "doctrine_connection": "A doutrina ensina...", "reflection_questions": ["Q1?", "Q2?", "Q3?"], "is_closing": false}'


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


@pytest.fixture(autouse=True)
def _default_sensitivity_normal(monkeypatch):
    monkeypatch.setattr("src.rag.reflect.classify_sensitivity", lambda t: "normal")


def test_reflect_returns_not_found_when_no_chunks():
    with patch("src.rag.reflect.retrieve", return_value=[]):
        result = reflect("meu pai faleceu")
    assert result["not_found"] is True
    assert result["generation_failed"] is False
    assert result["opening"] == ""
    assert result["complementary_items"] == []
    assert result["sources"] == []


def test_reflect_returns_opening_from_llm():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("meu pai faleceu")
    assert result["opening"] == "Compreendemos sua dor."
    assert result["not_found"] is False


def test_reflect_returns_reflection_questions():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("meu pai faleceu")
    assert result["reflection_questions"] == ["Q1?", "Q2?", "Q3?"]


def test_reflect_sets_generation_failed_on_llm_error():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError(
            "API error"
        )
        result = reflect("situação")
    assert result["generation_failed"] is True
    assert result["opening"] == ""
    assert result["not_found"] is False


def test_reflect_sets_generation_failed_on_retrieval_error():
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    with patch("src.rag.reflect.retrieve", side_effect=_raise):
        result = reflect("situação")
    assert result["generation_failed"] is True
    assert result["not_found"] is False
    assert result["sources"] == []
    assert result["complementary_items"] == []


def test_reflect_sets_generation_failed_on_unparseable_llm_output():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response("isso não é JSON de forma alguma")
        )
        result = reflect("situação")
    assert result["generation_failed"] is True
    assert result["opening"] == ""
    assert result["doctrine_connection"] == ""
    assert result["not_found"] is False


def test_reflect_returns_is_closing_from_llm():
    llm_json_closing = '{"opening": "Encerrando.", "doctrine_connection": "Conclusão.", "reflection_questions": [], "is_closing": true}'
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json_closing)
        )
        result = reflect("situação")
    assert result["is_closing"] is True
    assert result["reflection_questions"] == []


def test_reflect_passes_history_to_build_reflect_messages():
    history = [
        {"role": "user", "content": "pergunta anterior"},
        {"role": "assistant", "content": "resposta anterior"},
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("nova pergunta", conversation_history=history)
    assert mock_build.call_args.kwargs["history"] == history


def test_reflect_caveat_persists_from_history():
    history = [
        {"role": "user", "content": "escuto vozes à noite"},
        {"role": "assistant", "content": "Resposta anterior."},
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("situação neutra agora", conversation_history=history)
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is True


def test_reflect_forces_closing_after_round_cap():
    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"pergunta {i}"})
        history.append({"role": "assistant", "content": f"resposta {i}"})
    llm_json_not_closing = '{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"], "is_closing": false}'
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json_not_closing)
        )
        result = reflect("pergunta final", conversation_history=history)
    assert result["is_closing"] is True
    assert result["reflection_questions"] == []


def test_reflect_does_not_force_closing_below_round_cap():
    history = []
    for i in range(4):
        history.append({"role": "user", "content": f"pergunta {i}"})
        history.append({"role": "assistant", "content": f"resposta {i}"})
    llm_json_not_closing = '{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"], "is_closing": false}'
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json_not_closing)
        )
        result = reflect("pergunta", conversation_history=history)
    assert result["is_closing"] is False
    assert result["reflection_questions"] == ["C?"]


def test_reflect_sources_come_from_first_two_chunks():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2, _CHUNK_3]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação")
    assert len(result["sources"]) == 2
    item_numbers = [s["item_number"] for s in result["sources"]]
    assert "150" in item_numbers
    assert "132" in item_numbers


def test_reflect_complementary_items_come_from_chunks_3_to_5():
    extra = [
        {
            "content": f"texto {i}",
            "metadata": {"book": "Livro X", "item_number": str(i), "chapter_title": ""},
            "distance": 0.9,
        }
        for i in range(3, 6)
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2] + extra),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação")
    assert len(result["complementary_items"]) == 3
    assert result["complementary_items"][0]["item_number"] == "3"


def test_reflect_passes_add_caveat_true_for_clinical_keywords():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("escuto vozes à noite")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is True


def test_reflect_passes_add_caveat_false_for_normal_situation():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("meu pai faleceu")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is False


def test_reflect_sources_include_excerpt():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação")
    excerpts = [s["excerpt"] for s in result["sources"]]
    assert "Os espíritos sobrevivem à morte do corpo." in excerpts


def test_reflect_condenses_query_when_history_present():
    history = [
        {"role": "user", "content": "situação original"},
        {"role": "assistant", "content": "reflexão anterior"},
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch(
            "src.rag.reflect.condense_query", return_value="consulta condensada"
        ) as mock_cond,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("e se ela não me perdoar?", conversation_history=history)
    mock_cond.assert_called_once()
    assert mock_retrieve.call_args[0][0] == "consulta condensada"


def test_reflect_skips_condense_without_history():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.condense_query") as mock_cond,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("minha situação")
    mock_cond.assert_not_called()
    assert mock_retrieve.call_args[0][0] == "minha situação"


def test_reflect_falls_back_to_raw_situation_when_condense_fails():
    history = [{"role": "user", "content": "anterior"}]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.condense_query", side_effect=RuntimeError("down")),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação atual", conversation_history=history)
    assert mock_retrieve.call_args[0][0] == "situação atual"
    assert result["generation_failed"] is False


def test_reflect_no_crisis_note_for_normal_situation():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("meu pai faleceu")
    assert "CVV" not in result["doctrine_connection"]


def test_reflect_abalo_triggers_medical_caveat(monkeypatch):
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.classify_sensitivity", lambda t: "abalo"),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("estou cansada e não aguento mais")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is True


def test_reflect_passes_force_closing_to_prompt_at_cap():
    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"pergunta {i}"})
        history.append({"role": "assistant", "content": f"resposta {i}"})
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("pergunta final", conversation_history=history)
    assert mock_build.call_args.kwargs["force_closing"] is True


def test_reflect_passes_force_closing_false_below_cap():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("primeira situação")
    assert mock_build.call_args.kwargs["force_closing"] is False


def test_reflect_logs_on_retrieval_error(caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    with (
        patch("src.rag.reflect.retrieve", side_effect=_raise),
        caplog.at_level(logging.ERROR, logger="src.rag.reflect"),
    ):
        reflect("situação")
    assert any("retriev" in r.message.lower() for r in caplog.records)


def test_reflect_blends_anchor_into_retrieval_query():
    captured = {}

    def _capture(query, **kw):
        captured["query"] = query
        return [_CHUNK_1, _CHUNK_2]

    with (
        patch("src.rag.reflect.retrieve", _capture),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("preciso ser criança?", anchor_text="passagem sobre humildade")
    assert "passagem sobre humildade" in captured["query"]


def test_reflect_anchor_never_leaks_into_sources():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação", anchor_text="TEXTO ÂNCORA EXCLUSIVO")
    for source in result["sources"]:
        assert source["excerpt"] != "TEXTO ÂNCORA EXCLUSIVO"


def test_reflect_enriches_evangelho_top_hit():
    ev = {
        "content": "verso da parábola",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter": "CAPÍTULO XX",
            "chapter_title": "OS TRABALHADORES",
            "item_number": "1",
        },
    }

    def _spy_append(passages):
        passages.append(
            {
                "content": "comentario kardec",
                "metadata": {
                    "book": "O Evangelho Segundo o Espiritismo",
                    "chapter_title": "OS TRABALHADORES",
                    "item_number": "2",
                },
            }
        )
        return passages

    with (
        patch("src.rag.reflect.retrieve", return_value=[ev]),
        patch("src.rag.reflect.append_chapter_commentary", _spy_append),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("estou refletindo sobre a parábola")
    excerpts = [s["excerpt"] for s in result["sources"]]
    assert "comentario kardec" in excerpts


def test_reflect_keyword_crisis_returns_fixed_exit(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("classifier/retrieval must not run on keyword crisis")

    monkeypatch.setattr("src.rag.reflect.classify_sensitivity", _boom)
    monkeypatch.setattr("src.rag.reflect.retrieve", _boom)
    result = reflect("não quero mais viver")
    assert result["safety_level"] == "crise"
    assert "188" in result["doctrine_connection"]
    assert result["sources"] == []
    assert result["reflection_questions"] == []


def test_reflect_llm_crise_returns_fixed_exit(monkeypatch):
    monkeypatch.setattr("src.rag.reflect.retrieve", lambda q, **kw: [_CHUNK_1])
    monkeypatch.setattr("src.rag.reflect.classify_sensitivity", lambda t: "crise")
    result = reflect("estou muito mal")
    assert result["safety_level"] == "crise"
    assert "188" in result["doctrine_connection"]
    assert result["sources"] == []


def test_reflect_abalo_filters_dark_chunks(monkeypatch):
    dark = {
        "content": "relato de suicida",
        "metadata": {
            "book": "O Céu e o Inferno",
            "chapter_title": "SUICIDAS",
            "item_number": "1",
        },
    }
    with (
        patch("src.rag.reflect.retrieve", return_value=[dark, _CHUNK_1]),
        patch("src.rag.reflect.classify_sensitivity", lambda t: "abalo"),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("estou cansada e não aguento mais")
    assert result["safety_level"] == "abalo"
    assert all(s["excerpt"] != "relato de suicida" for s in result["sources"])


def test_reflect_normal_carries_safety_level(monkeypatch):
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect.classify_sensitivity", lambda t: "normal"),
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.curar", return_value=[]),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("o que é a reencarnação?")
    assert result["safety_level"] == "normal"
    assert result["not_found"] is False
