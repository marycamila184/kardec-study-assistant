import json
from dataclasses import replace
from html import escape
from pathlib import Path

from src.discovery.content import Page, Passage
from src.discovery.render import (
    CABECALHO_FRASES,
    CHAT_LINK,
    HOST,
    deep_link,
    page_url,
    render_page,
    render_sitemap,
    trilha_link,
)

PASSAGE = Passage(
    book="O Céu e o Inferno",
    chapter="CAPÍTULO I",
    item_number="1",
    part="II PARTE",
    label="O passamento",
    text="Linha um\nLinha dois",
)

PAGE = Page(
    slug="o-que-acontece-depois-da-morte",
    kind="tema",
    title="O que acontece depois da morte, segundo a Doutrina Espírita",
    heading="O que acontece depois da morte?",
    meta_description="As passagens de Allan Kardec sobre o assunto.",
    intro="Enquadramento escrito por uma pessoa & revisado.",
    passages=[PASSAGE],
)


def test_url_has_the_trailing_slash():
    assert page_url(PAGE) == f"{HOST}/temas/o-que-acontece-depois-da-morte/"


def test_deep_link_carries_the_part():
    link = deep_link(PASSAGE)
    assert link.startswith(f"{HOST}/?")
    assert "book=O+C%C3%A9u+e+o+Inferno" in link
    assert "chapter=CAP%C3%8DTULO+I" in link
    assert "item=1" in link
    assert "part=II+PARTE" in link


def test_deep_link_omits_an_absent_part():
    without = Passage(
        book="A Gênese",
        chapter="CAPÍTULO III",
        item_number="46",
        part=None,
        label="x",
        text="y",
    )
    assert "part=" not in deep_link(without)


def test_page_has_no_javascript():
    assert "<script" not in render_page(PAGE).lower()


def test_page_canonical_and_og_url_agree_with_page_url():
    html = render_page(PAGE)
    url = page_url(PAGE)
    assert f'<link rel="canonical" href="{url}">' in html
    assert f'<meta property="og:url" content="{url}">' in html


def test_page_escapes_content():
    html = render_page(PAGE)
    assert "&amp;" in html  # the intro's ampersand
    assert "pessoa & revisado" not in html


def test_page_shows_the_passage_and_links_into_the_app():
    html = render_page(PAGE)
    assert "Linha um\nLinha dois" in html
    assert deep_link(PASSAGE).replace("&", "&amp;") in html


def test_sitemap_lists_home_sobre_and_every_page():
    xml = render_sitemap([PAGE])
    assert f"<loc>{HOST}/</loc>" in xml
    assert f"<loc>{HOST}/sobre/</loc>" in xml
    assert f"<loc>{page_url(PAGE)}</loc>" in xml


SEGUNDA = Passage(
    book="O Evangelho Segundo o Espiritismo",
    chapter="CAPÍTULO II",
    item_number="1",
    part=None,
    label="Pilatos",
    text="Texto do segundo trecho",
)

TRILHA = Page(
    slug="fundamentos-evangelico-curioso",
    kind="trilha",
    title="Fundamentos do Evangelho Segundo o Espiritismo — Dialogando com a Doutrina",
    heading="Fundamentos do Evangelho Segundo o Espiritismo",
    meta_description="Para quem está começando.",
    intro="Para quem está começando.",
    passages=[PASSAGE, SEGUNDA],
)


def test_a_trilha_offers_both_doors():
    html = render_page(TRILHA)
    assert f'href="{CHAT_LINK}"' in html
    assert "Dialogar" in html
    assert "Estudar esta trilha" in html


def test_the_study_door_names_the_trilha_by_its_slug():
    """O slug da página É o id da trilha, e startTrilha só precisa do id."""
    assert trilha_link(TRILHA) == f"{HOST}/?trilha=fundamentos-evangelico-curioso"
    assert f'href="{trilha_link(TRILHA)}"' in render_page(TRILHA)


def test_the_study_door_counts_the_passages():
    """Sem número escrito à mão: ele envelheceria junto com a curadoria."""
    assert "Os 2 trechos, um por vez, no app" in render_page(TRILHA)


def test_the_study_door_says_it_in_the_singular_for_one_passage():
    one = replace(TRILHA, passages=[PASSAGE])  # from dataclasses import replace
    assert "Um trecho, no app" in render_page(one)
    assert "Os 1 trechos" not in render_page(one)


def test_a_tema_offers_only_the_chat_door():
    """?trilha=<slug-de-tema> nomearia um id que não existe em data/paths/,
    e o leitor cairia no picker sem entender por quê."""
    html = render_page(PAGE)  # PAGE.kind == "tema"
    assert f'href="{CHAT_LINK}"' in html
    assert "?trilha=" not in html
    assert "Estudar esta trilha" not in html


def test_the_doors_come_before_the_passages():
    """O ponto inteiro: a pessoa vê as portas antes de rolar 22 trechos."""
    html = render_page(TRILHA)
    assert html.index("Dialogar") < html.index("Texto do segundo trecho")


def test_the_doors_carry_no_javascript():
    assert "<script" not in render_page(TRILHA).lower()
    assert "onclick" not in render_page(TRILHA).lower()


def test_the_sobre_page_reads_the_shared_sentences_from_the_json():
    """A Sobre virou uma rota Astro (frontend/src/pages/sobre.astro) que
    importa frases.json e interpola `{frases.chave}` — ela não copia mais o
    texto à mão, então a checagem que existia aqui até 2026-08-09 (comparar a
    Sobre e o JSON frase a frase, para pegar uma cópia truncada ou reescrita)
    não tem mais o que comparar: os dois lados são o mesmo valor por
    construção, e uma cópia divergente é estruturalmente impossível enquanto
    a página ler o JSON em vez de repetir o texto.

    O que ainda pode quebrar — e o que esta versão guarda — é a página voltar
    a hardcodar a frase (ex.: colar o texto de volta em vez de `{frases.
    o_que_e}`), o que reabriria exatamente o risco de duas cópias divergentes
    que a JSON existe para fechar. Por isso a checagem agora é estrutural:
    cada chave usada na Sobre precisa aparecer como `{frases.<chave>}` no
    arquivo-fonte. Isto não confere o HTML renderizado (isso pediria buildar
    o Astro antes de rodar pytest, uma dependência que este arquivo de teste
    não tinha e que a suíte Python não deveria carregar) — confere que a
    fonte referencia o JSON em vez de duplicar o texto.
    """
    frases = json.loads(
        Path("frontend/src/content/frases.json").read_text(encoding="utf-8")
    )
    sobre = Path("frontend/src/pages/sobre.astro").read_text(encoding="utf-8")

    assert "import frases from '../content/frases.json'" in sobre

    for chave in (
        "o_que_e",
        "nao_substitui",
        "pode_errar",
        "separado_da_ia",
        "nao_encontrei",
        "so_estas_obras",
        "independente",
    ):
        assert chave in frases, f"chave {chave!r} não existe mais em frases.json"
        assert f"{{frases.{chave}}}" in sobre, (
            f"a Sobre não lê {chave!r} do JSON — o texto pode ter sido "
            "hardcodado de volta, reabrindo o risco de duas cópias divergentes"
        )


def test_the_python_header_reads_the_shared_file():
    """Uma origem só: se o JSON mudar, o cabeçalho das trilhas muda junto."""
    frases = json.loads(
        Path("frontend/src/content/frases.json").read_text(encoding="utf-8")
    )
    assert CABECALHO_FRASES == (
        frases["o_que_e"],
        frases["nao_substitui"],
        frases["pode_errar"],
    )


def test_every_page_carries_the_header():
    for page in (PAGE, TRILHA):
        html = render_page(page)
        assert 'class="cabecalho"' in html
        for frase in CABECALHO_FRASES:
            assert escape(frase) in html


def test_the_header_links_to_the_app_and_to_sobre():
    html = render_page(TRILHA)
    header = html[html.index('<header class="cabecalho">') : html.index("</header>")]
    assert f'href="{HOST}/"' in header
    assert f'href="{HOST}/sobre/"' in header
    assert 'class="cabecalho-nome"' in header
    assert 'class="cabecalho-mais"' in header


def test_the_h1_is_the_page_heading_not_the_project_name():
    """O <h1> é o que o buscador lê como assunto da página, e o assunto é a
    trilha — não o site."""
    html = render_page(TRILHA)
    assert f"<h1>{escape(TRILHA.heading)}</h1>" in html
    assert "<h1>Dialogando com a Doutrina</h1>" not in html


def test_the_header_comes_before_the_h1():
    html = render_page(TRILHA)
    assert html.index('class="cabecalho"') < html.index("<h1>")


def test_the_first_passage_is_open_and_the_rest_are_not():
    html = render_page(TRILHA)
    assert html.count('<details class="passagem" open>') == 1
    assert html.count('<details class="passagem">') == len(TRILHA.passages) - 1


def test_every_passage_text_is_still_in_the_file():
    """Recolher esconde na tela, nunca no arquivo.

    É o texto dos trechos que casa com a busca de alguém — é a razão inteira
    de estas páginas existirem. Um <details> mantém o texto no HTML; um
    acordeão em JavaScript não manteria.
    """
    html = render_page(TRILHA)
    for passage in TRILHA.passages:
        assert escape(passage.text) in html


def test_the_summary_carries_the_label_and_the_reference():
    html = render_page(TRILHA)
    assert '<summary class="resumo">' in html
    assert escape(PASSAGE.label) in html
    assert "O Céu e o Inferno" in html  # o livro, na referência


def test_each_passage_keeps_its_own_link_into_the_app():
    html = render_page(TRILHA)
    assert html.count('class="abrir"') == len(TRILHA.passages)


def test_the_passages_carry_no_javascript():
    html = render_page(TRILHA).lower()
    assert "<script" not in html
    assert "onclick" not in html
