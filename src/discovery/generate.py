"""Writes the discovery artefacts: the trilha content JSON the Astro route
reads, plus the static tema pages under frontend/public/ and the sitemap.

Build-time only, and its output is committed — Astro copies public/ into dist/
verbatim, so nothing here runs at deploy time. Run it when content changes:

    uv run python -m src.discovery.generate
"""

import json
import os
import shutil

from src.discovery.content import load_pages
from src.discovery.corpus import load_corpus
from src.discovery.export import trilha_content
from src.discovery.render import render_page, render_sitemap

JSON_DIR = "data/json_files"
TOPICS_DIR = "data/topics"
PATHS_DIR = "data/paths"
OUT_DIR = "frontend/public"
CONTENT_DIR = "frontend/src/content/trilhas"
# "trilhas" continua aqui depois da Fase 2 de propósito: nada mais escreve essa
# árvore, e limpá-la é o que apaga as páginas antigas num checkout que ainda as
# carregue — exatamente a falha silenciosa que esta limpeza existe para evitar.
GENERATED = ("temas", "trilhas")


def generate(
    json_dir: str = JSON_DIR,
    topics_dir: str = TOPICS_DIR,
    paths_dir: str = PATHS_DIR,
    out_dir: str = OUT_DIR,
    content_dir: str = CONTENT_DIR,
) -> list[str]:
    index = load_corpus(json_dir)
    pages = load_pages(topics_dir, paths_dir, index)

    # Renaming a topic would otherwise leave the old directory live and
    # unreferenced — a page nobody links to and nobody knows is there. Only the
    # two generated trees are cleared; /sobre/, preview.png and robots.txt are
    # hand-written and must survive.
    #
    # Precisa existir mesmo sem nenhum tema: desde a Fase 2 uma trilha não
    # escreve mais nada dentro de out_dir (só no content_dir), então quando o
    # corpus não tem tema nenhum — o caso de hoje, data/topics/ está vazio —
    # nada mais cria out_dir como efeito colateral, e o sitemap.xml escrito no
    # fim desta função falharia por diretório ausente.
    os.makedirs(out_dir, exist_ok=True)
    for name in GENERATED:
        shutil.rmtree(os.path.join(out_dir, name), ignore_errors=True)
    # Mesmo motivo, no lado novo: um slug renomeado deixaria o JSON antigo
    # para trás, e getStaticPaths() construiria uma rota para uma trilha que
    # data/paths/ não tem mais.
    shutil.rmtree(content_dir, ignore_errors=True)
    os.makedirs(content_dir, exist_ok=True)

    written = []
    for page in pages:
        if page.kind == "trilha":
            # Desde a Fase 2 a trilha é uma rota Astro
            # (frontend/src/pages/trilhas/[slug].astro) que lê o JSON abaixo.
            # Escrever HTML aqui também colidiria com ela em dist/, e uma das
            # duas venceria em silêncio.
            content = os.path.join(content_dir, f"{page.slug}.json")
            with open(content, "w", encoding="utf-8") as f:
                json.dump(trilha_content(page), f, ensure_ascii=False, indent=2)
                f.write("\n")
            written.append(content)
            continue

        directory = os.path.join(out_dir, f"{page.kind}s", page.slug)
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, "index.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(render_page(page))
        written.append(filepath)

    sitemap = os.path.join(out_dir, "sitemap.xml")
    with open(sitemap, "w", encoding="utf-8") as f:
        f.write(render_sitemap(pages))
    written.append(sitemap)
    return written


def main() -> None:
    written = generate()
    for path in written:
        print(f"escrito: {path}")
    print(f"{len(written)} arquivos.")


if __name__ == "__main__":
    main()
