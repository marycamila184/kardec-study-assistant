from src.discovery.content import Page, Passage
from src.discovery.render import (
    HOST,
    deep_link,
    page_url,
    render_page,
    render_sitemap,
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
