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
    assert "OUTROS ITENS DESTE CAPÍTULO" in system
    assert "O obreiro da última hora tem direito ao salário." in system


def test_explicador_prompt_omits_commentary_block_content_when_empty():
    system, _ = build_explicador_messages("verso", [], chapter_commentary_chunks=None)
    assert "(nenhuma)" in system  # block present but marked empty, no crash


def test_explicador_prompt_has_evangelical_grounding_rule():
    system, _ = build_explicador_messages("verso", [])
    assert "texto evangélico" in system
    assert "OUTROS ITENS DESTE CAPÍTULO" in system


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


def test_chapter_section_makes_no_claim_about_whose_voice_it_is():
    """A seção traz versículo e comentário misturados — nada no metadata os
    separa. Chamá-la de "comentário doutrinário" faz o modelo apresentar
    escritura como palavra de Kardec, que foi o que aconteceu em 2026-07-28
    com o item 2 do capítulo AMAI OS VOSSOS INIMIGOS (itens 1 e 2 são
    Evangelho; Kardec começa no 3).

    build_chapter_context em explicador.py já tinha chegado nessa conclusão e
    é neutro por escolha; agora o prompt concorda com ele.
    """
    system, _ = build_explicador_messages(
        "1. Aprendestes que foi dito…",
        [],
        chapter_commentary_chunks=[
            {
                "content": "2. Se somente amardes os que vos amam…",
                "metadata": {
                    "book": "O Evangelho Segundo o Espiritismo",
                    "item_number": "2",
                },
            }
        ],
    )
    assert "OUTROS ITENS DESTE CAPÍTULO" in system
    assert "COMENTÁRIO DOUTRINÁRIO" not in system


def test_related_passages_are_not_shaped_like_markable_items():
    """As relacionadas cruzam capítulos; os itens do capítulo, não.

    Enquanto as duas listas saíam no mesmo formato, "use apenas números desta
    seção" era uma regra que o modelo tinha de cumprir de memória. Em
    2026-07-28 o ESE item 50, de "Pelos inimigos do Espiritismo", foi citado
    como se fosse deste capítulo.
    """
    chapter = [
        {
            "content": "3. Se o amor do próximo…",
            "metadata": {
                "book": "O Evangelho Segundo o Espiritismo",
                "item_number": "3",
            },
        }
    ]
    related = [
        {
            "content": "50. Bem-aventurados os famintos de justiça…",
            "metadata": {
                "book": "O Evangelho Segundo o Espiritismo",
                "item_number": "50",
            },
        }
    ]
    system, _ = build_explicador_messages(
        "1. Aprendestes…",
        related_chunks=related,
        chapter_commentary_chunks=chapter,
    )
    # rsplit: os dois nomes de seção aparecem antes, dentro das regras — o
    # bloco de verdade é sempre a ÚLTIMA ocorrência.
    chapter_block = system.rsplit("[OUTROS ITENS DESTE CAPÍTULO]", 1)[1].rsplit(
        "[REFERÊNCIAS RELACIONADAS]", 1
    )[0]
    related_block = system.rsplit("[REFERÊNCIAS RELACIONADAS]", 1)[1]

    # O item do capítulo sai na forma exata do marcador que se pede: copiar em
    # vez de lembrar.
    assert "[item 3]" in chapter_block
    # A relacionada não traz número em forma citável.
    assert "[item 50]" not in related_block
    assert "| item 50]" not in related_block
