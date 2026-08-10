import json
import os
from pathlib import Path

import pytest

from src.discovery.content import Page, Passage
from src.discovery.export import trilha_content

PASSAGE = Passage(
    book="O Céu e o Inferno",
    chapter="CAPÍTULO I",
    item_number="1",
    part="I PARTE",
    label="O porvir e o nada",
    text="Primeira linha.\nSegunda linha.",
)

PAGE = Page(
    slug="uma-trilha",
    kind="trilha",
    title="Uma trilha — Dialogando com a Doutrina",
    heading="Uma trilha",
    meta_description="Uma linha de resumo.",
    intro="Uma linha de resumo.",
    passages=[PASSAGE],
)


def test_the_json_carries_every_field_the_route_reads():
    """A rota Astro lê estas chaves e mais nenhuma.

    Uma chave renomeada aqui não quebra o build do Astro: `trilha.titulo` de
    uma chave inexistente vira `undefined` e a página sai com um <h1> vazio,
    válida e silenciosa. Este teste é o que impede a renomeação de passar.
    """
    conteudo = trilha_content(PAGE)
    assert conteudo["id"] == "uma-trilha"
    assert conteudo["title"] == "Uma trilha"
    assert conteudo["meta_title"] == "Uma trilha — Dialogando com a Doutrina"
    assert conteudo["meta_description"] == "Uma linha de resumo."
    assert conteudo["intro"] == "Uma linha de resumo."
    assert conteudo["passages"] == [
        {
            "book": "O Céu e o Inferno",
            "chapter": "CAPÍTULO I",
            "item_number": "1",
            "part": "I PARTE",
            "label": "O porvir e o nada",
            "text": "Primeira linha.\nSegunda linha.",
        }
    ]


def test_part_survives_as_null_when_absent():
    """`None` significa "não filtrar", e tem de chegar ao JSON como null.

    Omitir a chave faria a rota emitir um deep link sem `part` — que é o
    comportamento certo — mas por acidente, e a diferença some no diff. O Céu e
    o Inferno tem 14 chaves que colidem sem `part`.
    """
    sem_parte = Passage(
        book="O Livro dos Espíritos",
        chapter=None,
        item_number="1",
        part=None,
        label="Questão 1",
        text="Texto.",
    )
    conteudo = trilha_content(
        Page(
            slug="outra",
            kind="trilha",
            title="t",
            heading="h",
            meta_description="m",
            intro="i",
            passages=[sem_parte],
        )
    )
    assert conteudo["passages"][0]["part"] is None
    assert conteudo["passages"][0]["chapter"] is None


def test_the_json_is_utf8_and_readable_in_a_diff():
    """Escrito com ensure_ascii=False: o diff mostra "Espíritos", não \\u00ed.

    O arquivo é commitado e revisado à mão; um diff ilegível é um diff que
    ninguém lê.
    """
    texto = json.dumps(trilha_content(PAGE), ensure_ascii=False, indent=2)
    assert "Céu" in texto
