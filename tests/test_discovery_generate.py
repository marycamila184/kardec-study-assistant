import json
import os

import pytest

from src.discovery.generate import generate

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
    """Topic dir with one topic, an EMPTY paths dir, and an output dir.

    The paths dir is empty because the real trilhas range over the whole
    Evangelho, which the fixture corpus does not carry. Trilha generation is
    covered by the full-corpus test below.
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
    return str(topics), str(paths), str(out)


def test_writes_a_directory_index_and_a_sitemap(tmp_path):
    topics, paths, out = _dirs(tmp_path)
    written = generate(FIXTURE_DIR, topics, paths, out)
    page = os.path.join(out, "temas", "o-que-e-perispirito", "index.html")
    assert os.path.exists(page)
    assert os.path.exists(os.path.join(out, "sitemap.xml"))
    assert page in written


def test_removes_pages_whose_source_file_is_gone(tmp_path):
    topics, paths, out = _dirs(tmp_path)
    stale = os.path.join(out, "temas", "tema-antigo")
    os.makedirs(stale)
    with open(os.path.join(stale, "index.html"), "w", encoding="utf-8") as f:
        f.write("<p>antigo</p>")
    generate(FIXTURE_DIR, topics, paths, out)
    assert not os.path.exists(stale)


def test_leaves_sobre_and_preview_untouched(tmp_path):
    topics, paths, out = _dirs(tmp_path)
    sobre = os.path.join(out, "sobre")
    os.makedirs(sobre)
    with open(os.path.join(sobre, "index.html"), "w", encoding="utf-8") as f:
        f.write("<p>sobre</p>")
    generate(FIXTURE_DIR, topics, paths, out)
    assert os.path.exists(os.path.join(sobre, "index.html"))


@needs_full_corpus
def test_writes_a_page_per_trilha(tmp_path):
    topics, _, out = _dirs(tmp_path)
    generate(FULL_CORPUS, topics, "data/paths", out)
    trilhas = os.listdir(os.path.join(out, "trilhas"))
    assert len(trilhas) == len(
        [f for f in os.listdir("data/paths") if f.endswith(".json")]
    )
