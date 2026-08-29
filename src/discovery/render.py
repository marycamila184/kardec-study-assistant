"""Page HTML. No template engine, no JavaScript, no model output.

The <head> and the palette mirror frontend/src/pages/sobre.astro so these
pages belong to the same site in both colour schemes. Like that page they
carry no script: the whole point is that a reader sees the text before any
bundle loads and a crawler sees text instead of an empty root div.

Mirroring includes the manifest and icon links. These pages do not go through
Base.astro — this file writes its own <head> — so anything added there has to
be added here by hand or the two drift. They are landing pages arriving from
search, which makes them exactly the pages someone might want to install from,
and scripts/check_pwa_manifest.mjs requires the links on every built page
without exception. A <link> is not a script, so the no-script rule above is
untouched.
"""

import json
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from src.discovery.content import Page, Passage

HOST = "https://dialogandodoutrina.com.br"

# A porta do chat. O app lê `mode` no boot; `duvida` é o id persistido do
# modo Dialogar (constants/modes.js) e NUNCA deve ser renomeado.
CHAT_LINK = f"{HOST}/?mode=duvida"

# As frases vivem em frontend/src/content/frases.json porque três páginas as
# usam: a home e a Sobre (ambas Astro) e o cabeçalho das trilhas (aqui). Antes
# desta leitura elas existiam em duas cópias vigiadas por um teste anti-deriva;
# uma origem só torna a deriva impossível em vez de vigiada.
#
# A origem do texto continua sendo a página Sobre, escrita por uma pessoa —
# test_the_sentences_are_copied_from_the_sobre_page guarda isso.
#
# Uma frase da Sobre fica de fora de propósito: a segunda frase de "Limites e
# cuidados" — "Se a explicação e o trecho citado divergirem, vale o
# trecho…" — não entra em frases.json (decisão da autora, 2026-08-09). Ela
# instrui a conferir a citação dentro do app, e quem ainda não entrou não tem
# o que conferir.
_FRASES_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "content" / "frases.json"
)

with open(_FRASES_PATH, encoding="utf-8") as _f:
    _FRASES = json.load(_f)

CABECALHO_FRASES = (
    _FRASES["o_que_e"],
    _FRASES["nao_substitui"],
    _FRASES["pode_errar"],
)

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
  .cabecalho {
    max-width: 42rem; margin: 0 auto 2rem; padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--borda);
  }
  .cabecalho-nome {
    font-family: 'Crimson Pro', Georgia, serif; font-weight: 600;
    font-size: 1.15rem; color: var(--texto); text-decoration: none;
    display: inline-block; margin-bottom: .6rem;
  }
  .cabecalho p { margin: 0 0 .5rem; color: var(--suave); font-size: .93rem; }
  .cabecalho-limites { color: var(--tenue); font-size: .88rem; }
  .cabecalho-mais {
    color: var(--azul); text-decoration: none; font-size: .88rem;
  }
  .cabecalho-mais:hover { text-decoration: underline; }
  h1 {
    font-family: 'Crimson Pro', Georgia, serif; font-weight: 600;
    font-size: 1.9rem; line-height: 1.25; margin: 0 0 1rem;
  }
  .intro { color: var(--suave); margin: 0 0 1.5rem; }
  /* O cartão da home do app: mesmo fundo, borda, raio e espaçamento que
     HomeLauncher usa, para a página ser reconhecivelmente a mesma casa. */
  .portas { display: flex; flex-direction: column; gap: .75rem; margin: 0 0 2.5rem; }
  .porta {
    display: flex; align-items: center; gap: .9rem;
    background: var(--cartao); border: 1px solid var(--borda);
    border-radius: 12px; padding: 1rem 1.15rem;
    text-decoration: none; color: inherit;
  }
  .porta:hover, .porta:focus-visible { border-color: var(--azul); }
  .porta-icone { font-size: 1.35rem; line-height: 1; }
  .porta-texto { display: flex; flex-direction: column; }
  .porta-nome { font-weight: 500; }
  .porta-desc { font-size: .88rem; color: var(--suave); }
  .passagem {
    background: var(--obra-fundo); border: 1px solid var(--obra-borda);
    border-radius: 10px; padding: 1.1rem 1.25rem; margin: 0 0 .75rem;
  }
  .resumo { cursor: pointer; }
  .resumo-rotulo { display: block; font-weight: 500; }
  .resumo-ref {
    display: block; font-size: .82rem; text-transform: uppercase;
    letter-spacing: .06em; color: var(--tenue); margin-top: .25rem;
  }
  .passagem[open] .resumo { margin-bottom: .9rem; }
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


def trilha_link(page: Page) -> str:
    """Into the trilha itself.

    The page slug IS the trilha id: generate.py writes trilhas/<slug>/ from
    data/paths/<slug>.json, whose `id` field is that same slug. App.jsx calls
    startTrilha({id}), which fetches the path detail itself — so nothing else
    has to travel, and nothing has to wait for getPaths() to land.

    No quoting: content.SLUG already restricts a slug to [a-z0-9-].
    """
    return f"{HOST}/?trilha={page.slug}"


def _porta(href: str, icone: str, nome: str, desc: str) -> str:
    return f"""<a class="porta" href="{escape(href)}">
<span class="porta-icone" aria-hidden="true">{icone}</span>
<span class="porta-texto"><span class="porta-nome">{escape(nome)}</span><span class="porta-desc">{escape(desc)}</span></span>
</a>"""


def _portas_html(page: Page) -> str:
    """A tela inicial do app, em HTML estático.

    Quem chega de um buscador veio com uma pergunta, não para ler 22 trechos.
    HomeLauncher oferece exatamente duas entradas — Dialogar e Estudar — e a
    porta as reproduz antes da parede de texto.

    Um `tema` recebe só a porta do Dialogar: ?trilha=<slug-de-tema> nomearia um
    id inexistente em data/paths/ e o leitor cairia no picker sem entender.
    """
    portas = [_porta(CHAT_LINK, "💬", "Dialogar", "Faça uma pergunta sobre as obras")]
    if page.kind == "trilha":
        n = len(page.passages)
        desc = "Um trecho, no app" if n == 1 else f"Os {n} trechos, um por vez, no app"
        portas.append(_porta(trilha_link(page), "📚", "Estudar esta trilha", desc))
    return '<div class="portas">\n' + "\n".join(portas) + "\n</div>"


def _passage_html(passage: Passage, aberto: bool = False) -> str:
    """Um trecho, recolhido.

    <details> em vez de <article> porque a página abria com 22 trechos e o
    leitor tinha de rolar para descobrir que existe um app. O texto continua
    inteiro no arquivo — o buscador indexa conteúdo dentro de <details>; o que
    ele desvaloriza é conteúdo que só chega depois de um clique, buscado por
    JavaScript. É por isso que aqui é HTML nativo e não um acordeão em script.

    O marcador nativo do <details> fica: os cartões do app não têm triângulo,
    mas ali nada expande, e sem ele o leitor conclui que a página só tem
    títulos. Ele traz teclado e leitor de tela sem custo.
    """
    ref = passage.label
    where = passage.chapter or ""
    if passage.part:
        where = f"{passage.part}, {where}"
    caption = f"{passage.book} — {where} item {passage.item_number}".strip()
    marca = " open" if aberto else ""
    return f"""<details class="passagem"{marca}>
<summary class="resumo"><span class="resumo-rotulo">{escape(ref)}</span><span class="resumo-ref">{escape(caption)}</span></summary>
<p class="texto">{escape(passage.text)}</p>
<a class="abrir" href="{escape(deep_link(passage))}">Abrir “{escape(ref)}” no app &rarr;</a>
</details>"""


def _cabecalho_html() -> str:
    """Quem é este site, para quem nunca ouviu falar dele.

    Vem antes do <h1> e é idêntico em toda página. O <h1> continua sendo o
    título da página porque é ele que o buscador lê como o assunto.
    """
    o_que_e, nao_substitui, pode_errar = CABECALHO_FRASES
    return f"""<header class="cabecalho">
<a class="cabecalho-nome" href="{HOST}/">Dialogando com a Doutrina</a>
<p>{escape(o_que_e)}</p>
<p class="cabecalho-limites">{escape(nao_substitui)} {escape(pode_errar)}</p>
<a class="cabecalho-mais" href="{HOST}/sobre/">Sobre o projeto &rarr;</a>
</header>"""


def render_page(page: Page) -> str:
    url = page_url(page)
    # O primeiro vem aberto: quem chega vê texto real de imediato e entende o
    # que as linhas contêm, sem clicar — e a página não parece vazia.
    passages = "\n".join(
        _passage_html(p, aberto=(i == 0)) for i, p in enumerate(page.passages)
    )
    portas = _portas_html(page)
    cabecalho = _cabecalho_html()
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(page.title)}</title>
<meta name="description" content="{escape(page.meta_description)}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#6B9BB8">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
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
{cabecalho}
<main>
<h1>{escape(page.heading)}</h1>
<p class="intro">{escape(page.intro)}</p>
{portas}
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
