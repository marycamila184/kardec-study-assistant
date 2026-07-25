import json

from src.rag.explicador_prompt import build_explicador_messages, parse_explicador_json


def test_system_prohibits_personifying_espiritismo():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "espiritismo" in system.lower()


def test_system_allows_historical_context():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "histórico" in system.lower()


def test_system_still_forbids_doctrine_invention():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert (
        "nunca invente" in system.lower() or "nunca invente ou altere" in system.lower()
    )


def test_footnote_context_appears_in_system_when_provided():
    system, _ = build_explicador_messages(
        "Trecho.", [], footnote_context="[Nota 1] Explicação de exemplo."
    )
    assert "Explicação de exemplo." in system


def test_footnote_context_defaults_to_placeholder_when_empty():
    system, _ = build_explicador_messages("Trecho.", [])
    assert "(nenhuma)" in system


def test_system_instructs_using_related_references_for_contexto_depth():
    system, _ = build_explicador_messages("Trecho de exemplo.", [])
    assert "use também as referências relacionadas" in system.lower()


def test_parse_explicador_json_extracts_all_fields():
    text = json.dumps(
        {
            "contexto": "Contexto de teste.",
            "conceitos_chave": ["termo: definição"],
            "perguntas": ["Pergunta 1?"],
        }
    )
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert contexto == "Contexto de teste."
    assert conceitos == ["termo: definição"]
    assert perguntas == ["Pergunta 1?"]


def test_parse_explicador_json_strips_markdown_fences():
    text = (
        "```json\n"
        + json.dumps({"contexto": "C", "conceitos_chave": [], "perguntas": []})
        + "\n```"
    )
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert contexto == "C"


def test_parse_explicador_json_extracts_object_wrapped_in_prose():
    text = (
        "Aqui está o resultado: "
        + json.dumps({"contexto": "C", "conceitos_chave": [], "perguntas": ["P?"]})
        + " Espero que ajude."
    )
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert contexto == "C"
    assert perguntas == ["P?"]


def test_parse_explicador_json_fixes_malformed_conceitos_array():
    text = (
        '{"contexto": "C", '
        '"conceitos_chave": ["dever": "obrigação moral", "lei": "regra geral"], '
        '"perguntas": []}'
    )
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert conceitos == ["dever: obrigação moral", "lei: regra geral"]


def test_parse_explicador_json_handles_conceitos_as_list_of_dicts():
    text = json.dumps(
        {
            "contexto": "C",
            "conceitos_chave": [{"dever": "obrigação moral"}],
            "perguntas": [],
        }
    )
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert conceitos == ["dever: obrigação moral"]


def test_parse_explicador_json_falls_back_to_regex_extraction_on_unparseable_json():
    text = 'Resposta do modelo: "contexto": "Explicação via regex.", texto quebrado {[}'
    contexto, conceitos, perguntas = parse_explicador_json(text)
    assert contexto == "Explicação via regex."
    assert conceitos == []


def test_explicador_prompt_renders_chapter_commentary_block():
    commentary = [
        {
            "content": "O obreiro da última hora tem direito ao salário.",
            "metadata": {
                "book": "O Evangelho Segundo o Espiritismo",
                "item_number": "2",
            },
        }
    ]
    system, _ = build_explicador_messages(
        "verso da parábola", [], chapter_commentary_chunks=commentary
    )
    assert "COMENTÁRIO DOUTRINÁRIO DESTE CAPÍTULO" in system
    assert "O obreiro da última hora tem direito ao salário." in system


def test_explicador_prompt_omits_commentary_block_content_when_empty():
    system, _ = build_explicador_messages("verso", [], chapter_commentary_chunks=None)
    assert "(nenhuma)" in system  # block present but marked empty, no crash


def test_explicador_prompt_has_evangelical_grounding_rule():
    system, _ = build_explicador_messages("verso", [])
    assert "texto evangélico" in system
    assert "COMENTÁRIO DOUTRINÁRIO DESTE CAPÍTULO" in system


from src.rag.explicador_prompt import parse_explicador_markers


def test_parses_contexto_and_conceitos():
    text = (
        "CONTEXTO: Este item situa a lei de causa e efeito.\n"
        "CONCEITOS: dever: obrigação moral | lei natural: regra divina"
    )
    contexto, conceitos, perguntas = parse_explicador_markers(text)
    assert contexto == "Este item situa a lei de causa e efeito."
    assert conceitos == ["dever: obrigação moral", "lei natural: regra divina"]
    assert perguntas == []


def test_missing_conceitos_gives_empty_list():
    contexto, conceitos, _ = parse_explicador_markers("CONTEXTO: Apenas contexto.")
    assert contexto == "Apenas contexto."
    assert conceitos == []


def test_tolerates_bracketed_markers():
    text = "[CONTEXTO]: Um contexto.\n[CONCEITOS: a | b]"
    contexto, conceitos, _ = parse_explicador_markers(text)
    assert contexto == "Um contexto."
    assert conceitos == ["a", "b"]


def test_multiline_contexto():
    text = "CONTEXTO: Primeira frase.\nSegunda frase.\nCONCEITOS: a"
    contexto, _, _ = parse_explicador_markers(text)
    assert contexto == "Primeira frase.\nSegunda frase."


def test_unparseable_output_raises():
    """A caller must be able to treat garbage as a generation failure rather
    than leak raw model text to the user."""
    import pytest

    with pytest.raises(ValueError):
        parse_explicador_markers("uma resposta sem marcador nenhum")


def test_conceitos_capped_at_three():
    text = "CONTEXTO: c.\nCONCEITOS: a | b | c | d | e"
    _, conceitos, _ = parse_explicador_markers(text)
    assert len(conceitos) == 3
