"""Page HTML. No template engine, no JavaScript, no model output.

The <head> and the palette mirror frontend/public/sobre/index.html so these
pages belong to the same site in both colour schemes. Like that page they
carry no script: the whole point is that a reader sees the text before any
bundle loads and a crawler sees text instead of an empty root div.
"""

from html import escape
from urllib.parse import urlencode

from src.discovery.content import Page, Passage

HOST = "https://dialogandodoutrina.com.br"

_STYLE = """
  :root {
    --fundo: #F6F4EF; --cartao: #FFFFFF; --borda: #E2DDD6;
    --texto: #3A3028; --suave: #6A5E50; --tenue: #9A8E7E;
    --obra-fundo: #FBF8F2; --obra-borda: #DDD0B8;
    --azul: #6B9BB8;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --fundo: #111C26; --cartao: #1C2D3C; --borda: #253748;
      --texto: #D5CCC0; --suave: #B3A899; --tenue: #6A8898;
      --obra-fundo: #1E3040; --obra-borda: #2C4258;
      --azul: #8FB9D2;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2rem 1.25rem 4rem;
    background: var(--fundo); color: var(--texto);
    font-family: 'DM Sans', system-ui, sans-serif; font-weight: 300;
    line-height: 1.65;
  }
  main { max-width: 42rem; margin: 0 auto; }
  h1 {
    font-family: 'Crimson Pro', Georgia, serif; font-weight: 600;
    font-size: 1.9rem; line-height: 1.25; margin: 0 0 1rem;
  }
  .intro { color: var(--suave); margin: 0 0 2.5rem; }
  .passagem {
    background: var(--obra-fundo); border: 1px solid var(--obra-borda);
    border-radius: 10px; padding: 1.1rem 1.25rem; margin: 0 0 1.5rem;
  }
  .rotulo {
    font-size: .82rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--tenue); margin: 0 0 .6rem;
  }
  /* pre-wrap for the same reason ObraBlock uses it: join_subchunks emits
     single newlines that are the source's own paragraph breaks. */
  .texto { white-space: pre-wrap; margin: 0 0 .9rem; }
  .abrir { font-size: .9rem; color: var(--azul); text-decoration: none; }
  .abrir:hover { text-decoration: underline; }
  footer {
    max-width: 42rem; margin: 3rem auto 0; padding-top: 1.5rem;
    border-top: 1px solid var(--borda); color: var(--tenue); font-size: .9rem;
  }
  footer a { color: var(--azul); }
"""


def page_url(page: Page) -> str:
    """Absolute, with the trailing slash that makes the path match the file."""
    return f"{HOST}/{page.kind}s/{page.slug}/"


def deep_link(passage: Passage) -> str:
    """Into the app, on this exact passage.

    `part` travels with the rest — an identifier the app can lose nothing from
    is the whole promise. It is omitted when absent rather than sent empty, so
    the app sees no key instead of a falsy one.
    """
    params = {
        "book": passage.book,
        "chapter": passage.chapter or "",
        "item": passage.item_number,
    }
    if passage.part:
        params["part"] = passage.part
    return f"{HOST}/?{urlencode(params)}"


def _passage_html(passage: Passage) -> str:
    ref = passage.label
    where = passage.chapter or ""
    if passage.part:
        where = f"{passage.part}, {where}"
    caption = f"{passage.book} — {where} item {passage.item_number}".strip()
    return f"""<article class="passagem">
<p class="rotulo">{escape(caption)}</p>
<p class="texto">{escape(passage.text)}</p>
<a class="abrir" href="{escape(deep_link(passage))}">Abrir “{escape(ref)}” no app &rarr;</a>
</article>"""


def render_page(page: Page) -> str:
    url = page_url(page)
    passages = "\n".join(_passage_html(p) for p in page.passages)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(page.title)}</title>
<meta name="description" content="{escape(page.meta_description)}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#6B9BB8">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="Dialogando com a Doutrina">
<meta property="og:title" content="{escape(page.title)}">
<meta property="og:description" content="{escape(page.meta_description)}">
<meta property="og:image" content="{HOST}/preview.png">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@600&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
<style>{_STYLE}</style>
</head>
<body>
<main>
<h1>{escape(page.heading)}</h1>
<p class="intro">{escape(page.intro)}</p>
{passages}
</main>
<footer>
<p>As passagens acima são de Allan Kardec e estão em domínio público.
<a href="{HOST}/">Ir para o app</a> · <a href="{HOST}/sobre/">Sobre o projeto</a></p>
</footer>
</body>
</html>
"""


def render_sitemap(pages: list[Page]) -> str:
    entries = "\n".join(
        f"  <url>\n    <loc>{page_url(p)}</loc>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>0.7</priority>\n  </url>"
        for p in sorted(pages, key=page_url)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GERADO por src/discovery/generate.py. Não edite à mão: a lista cresce com
     data/topics/ e data/paths/, e uma entrada que não corresponde a um arquivo
     é uma falha silenciosa. -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{HOST}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{HOST}/sobre/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
{entries}
</urlset>
"""
