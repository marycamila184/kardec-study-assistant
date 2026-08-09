"""Writes the static discovery pages into frontend/public/.

Build-time only, and its output is committed — Vite copies public/ into dist/
verbatim, so nothing here runs at deploy time. Run it when content changes:

    uv run python -m src.discovery.generate
"""

import os
import shutil

from src.discovery.content import load_pages
from src.discovery.corpus import load_corpus
from src.discovery.render import render_page, render_sitemap

JSON_DIR = "data/json_files"
TOPICS_DIR = "data/topics"
PATHS_DIR = "data/paths"
OUT_DIR = "frontend/public"
GENERATED = ("temas", "trilhas")


def generate(
    json_dir: str = JSON_DIR,
    topics_dir: str = TOPICS_DIR,
    paths_dir: str = PATHS_DIR,
    out_dir: str = OUT_DIR,
) -> list[str]:
    index = load_corpus(json_dir)
    pages = load_pages(topics_dir, paths_dir, index)

    # Renaming a topic would otherwise leave the old directory live and
    # unreferenced — a page nobody links to and nobody knows is there. Only the
    # two generated trees are cleared; /sobre/, preview.png and robots.txt are
    # hand-written and must survive.
    for name in GENERATED:
        shutil.rmtree(os.path.join(out_dir, name), ignore_errors=True)

    written = []
    for page in pages:
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
