import json
import os
from pathlib import Path

import pytest

from src.discovery.generate import generate


def _slugs(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir()} if directory.is_dir() else set()


TOPIC = {
    "id": "o-que-e-perispirito",
    "question": "O que é o perispírito?",
    "title": "O que é o perispírito, segundo Allan Kardec",
    "meta_description": "As passagens sobre o corpo fluídico do Espírito.",
    "intro": "Enquadramento escrito por uma pessoa.",
    "steps": [
        {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter": "CAPÍTULO V",
            "item_number": "1",
            "part": None,
            "label": "Bem-aventurados os aflitos",
        }
    ],
}

FIXTURE_DIR = "tests/fixtures/discovery_corpus"
FULL_CORPUS = "data/json_files"

needs_full_corpus = pytest.mark.skipif(
    not os.path.isdir(FULL_CORPUS),
    reason="data/json_files/ is gitignored; run: uv run python -m src.parsing.parsing_pipeline",
)


def _dirs(tmp_path):
    """Topic dir with one topic, an EMPTY paths dir, an output dir and a
    content dir.

    The paths dir is empty because the real trilhas range over the whole
    Evangelho, which the fixture corpus does not carry. Trilha generation is
    covered by the full-corpus tests below.

    The content dir is a tmp_path one on purpose: generate() clears it, and a
    test that used the real frontend/src/content/trilhas/ would delete the six
    committed files as a side effect of running the suite.
    """
    topics = tmp_path / "topics"
    topics.mkdir()
    (topics / "o-que-e-perispirito.json").write_text(
        json.dumps(TOPIC, ensure_ascii=False), encoding="utf-8"
    )
    paths = tmp_path / "paths"
    paths.mkdir()
    out = tmp_path / "public"
    out.mkdir()
    content = tmp_path / "content"
    return str(topics), str(paths), str(out), str(content)


def test_writes_a_directory_index_and_a_sitemap(tmp_path):
    topics, paths, out, content = _dirs(tmp_path)
    written = generate(FIXTURE_DIR, topics, paths, out, content)
    page = os.path.join(out, "temas", "o-que-e-perispirito", "index.html")
    assert os.path.exists(page)
    assert os.path.exists(os.path.join(out, "sitemap.xml"))
    assert page in written


def test_removes_pages_whose_source_file_is_gone(tmp_path):
    topics, paths, out, content = _dirs(tmp_path)
    stale = os.path.join(out, "temas", "tema-antigo")
    os.makedirs(stale)
    with open(os.path.join(stale, "index.html"), "w", encoding="utf-8") as f:
        f.write("<p>antigo</p>")
    generate(FIXTURE_DIR, topics, paths, out, content)
    assert not os.path.exists(stale)


def test_leaves_sobre_and_preview_untouched(tmp_path):
    topics, paths, out, content = _dirs(tmp_path)
    sobre = os.path.join(out, "sobre")
    os.makedirs(sobre)
    with open(os.path.join(sobre, "index.html"), "w", encoding="utf-8") as f:
        f.write("<p>sobre</p>")
    generate(FIXTURE_DIR, topics, paths, out, content)
    assert os.path.exists(os.path.join(sobre, "index.html"))


@needs_full_corpus
def test_committed_pages_are_what_a_fresh_generation_produces(tmp_path):
    """The pages in frontend/public/ must still match their sources.

    This is the one failure the structural guard cannot see. Edit a trilha in
    data/paths/, forget `uv run python -m src.discovery.generate`, and the
    committed page keeps its correct canonical, keeps agreeing with the
    sitemap, and passes every check in check_discovery_assets.mjs — while
    serving content that no longer matches the curation. Nothing in the running
    app would ever surface it, which is exactly the kind of silent staleness
    this project guards against elsewhere.

    Skipped when data/json_files/ is absent (it is gitignored), so this runs
    for the person editing the curated data — who is the same person who has
    the parsed corpus.
    """
    out = tmp_path / "public"
    out.mkdir()
    content = tmp_path / "content"
    generate(FULL_CORPUS, "data/topics", "data/paths", str(out), str(content))

    live = Path("frontend/public")
    differences = []
    # Só "temas": as trilhas viraram rota Astro na Fase 2 e são guardadas por
    # test_committed_trilha_json_is_what_a_fresh_generation_produces.
    for family in ("temas",):
        fresh_slugs = _slugs(out / family)
        live_slugs = _slugs(live / family)
        if fresh_slugs != live_slugs:
            differences.append(
                f"{family}/: committed {sorted(live_slugs)} != "
                f"freshly generated {sorted(fresh_slugs)}"
            )
            continue
        for slug in sorted(fresh_slugs):
            a = (out / family / slug / "index.html").read_text(encoding="utf-8")
            b = (live / family / slug / "index.html").read_text(encoding="utf-8")
            if a != b:
                differences.append(f"{family}/{slug}/index.html is stale")

    fresh_sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    live_sitemap = (live / "sitemap.xml").read_text(encoding="utf-8")
    if fresh_sitemap != live_sitemap:
        differences.append("sitemap.xml is stale")

    assert not differences, (
        "committed discovery pages are out of date — run "
        "`uv run python -m src.discovery.generate`:\n  " + "\n  ".join(differences)
    )


@needs_full_corpus
def test_writes_a_page_per_trilha(tmp_path):
    """Desde a Fase 2 uma trilha não escreve HTML em out_dir — só o JSON em
    content_dir, que frontend/src/pages/trilhas/[slug].astro lê. out/trilhas/
    não existe mais; a contagem certa está no content_dir.
    """
    topics, _, out, content = _dirs(tmp_path)
    generate(FULL_CORPUS, topics, "data/paths", out, content)
    trilhas = [f for f in os.listdir(content) if f.endswith(".json")]
    assert len(trilhas) == len(
        [f for f in os.listdir("data/paths") if f.endswith(".json")]
    )


@needs_full_corpus
def test_committed_trilha_json_is_what_a_fresh_generation_produces(tmp_path):
    """O JSON commitado tem de continuar batendo com data/paths/ e o corpus.

    É a mesma falha que test_committed_pages_are_what_a_fresh_generation_
    produces guarda do outro lado, e ela ficou MAIS silenciosa depois da Fase
    2: editar data/paths/<slug>.json e esquecer o gerador publica uma rota
    Astro perfeitamente válida, com canonical certo, no sitemap, passando em
    todas as guardas — servindo curadoria antiga.
    """
    fresh = tmp_path / "content"
    generate(
        FULL_CORPUS, "data/topics", "data/paths", str(tmp_path / "public"), str(fresh)
    )

    live = Path("frontend/src/content/trilhas")
    differences = []
    fresh_slugs = {p.name for p in fresh.iterdir()}
    live_slugs = {p.name for p in live.iterdir()} if live.is_dir() else set()
    if fresh_slugs != live_slugs:
        differences.append(
            f"committed {sorted(live_slugs)} != freshly generated {sorted(fresh_slugs)}"
        )
    else:
        for name in sorted(fresh_slugs):
            a = (fresh / name).read_text(encoding="utf-8")
            b = (live / name).read_text(encoding="utf-8")
            if a != b:
                differences.append(f"{name} is stale")

    assert not differences, (
        "committed trilha content is out of date — run "
        "`uv run python -m src.discovery.generate`:\n  " + "\n  ".join(differences)
    )
