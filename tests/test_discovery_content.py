import json
import os

import pytest

from src.discovery.content import ContentError, load_pages
from src.discovery.corpus import load_corpus

FIXTURE_DIR = "tests/fixtures/discovery_corpus"
FULL_CORPUS = "data/json_files"

needs_full_corpus = pytest.mark.skipif(
    not os.path.isdir(FULL_CORPUS),
    reason="data/json_files/ is gitignored; run: uv run python -m src.parsing.parsing_pipeline",
)


@pytest.fixture(scope="module")
def index():
    return load_corpus(FIXTURE_DIR)


@pytest.fixture(scope="module")
def full_index():
    if not os.path.isdir(FULL_CORPUS):
        return {}
    return load_corpus(FULL_CORPUS)


def _dirs(tmp_path, **overrides):
    """A topics dir holding one topic, and an EMPTY paths dir.

    The paths dir is empty on purpose: the real trilhas range across books the
    fixture corpus does not carry, so pairing them with the fixture index would
    raise ContentError — and three tests below expect ContentError, which means
    they would pass for entirely the wrong reason. Trilha loading is covered by
    the full-corpus test instead.
    """
    topic = {
        "id": "o-que-acontece-depois-da-morte",
        "question": "O que acontece depois da morte?",
        "title": "O que acontece depois da morte, segundo a Doutrina Espírita",
        "meta_description": "As passagens de Allan Kardec sobre o assunto.",
        "intro": "Duas ou três frases de enquadramento escritas por uma pessoa.",
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
    topic.update(overrides)
    topics = tmp_path / "topics"
    topics.mkdir(exist_ok=True)
    (topics / f"{topic['id']}.json").write_text(
        json.dumps(topic, ensure_ascii=False), encoding="utf-8"
    )
    paths = tmp_path / "paths"
    paths.mkdir(exist_ok=True)
    return str(topics), str(paths)


def test_loads_a_topic_with_its_passage_text(tmp_path, index):
    topics, paths = _dirs(tmp_path)
    pages = load_pages(topics, paths, index)
    tema = next(p for p in pages if p.kind == "tema")
    assert tema.slug == "o-que-acontece-depois-da-morte"
    assert tema.heading == "O que acontece depois da morte?"
    assert tema.passages[0].text.strip()
    assert tema.passages[0].label == "Bem-aventurados os aflitos"


@needs_full_corpus
def test_loads_the_existing_trilhas(tmp_path, full_index):
    # The real trilhas point across the whole Evangelho, so this one needs the
    # full corpus. It is the test that proves every curated step still resolves
    # — a trilha step naming a passage that no longer exists is exactly the
    # silent breakage this catches.
    pages = load_pages(str(tmp_path), "data/paths", full_index)
    trilhas = [p for p in pages if p.kind == "trilha"]
    assert len(trilhas) == len(
        [f for f in os.listdir("data/paths") if f.endswith(".json")]
    )
    assert all(p.passages for p in trilhas)
    assert all(p.intro for p in trilhas)


def test_topic_without_intro_is_a_build_error(tmp_path, index):
    topics, paths = _dirs(tmp_path, intro="")
    with pytest.raises(ContentError, match="intro"):
        load_pages(topics, paths, index)


def test_topic_pointing_at_a_missing_passage_is_a_build_error(tmp_path, index):
    topics, paths = _dirs(
        tmp_path,
        steps=[
            {
                "book": "O Evangelho Segundo o Espiritismo",
                "chapter": "CAPÍTULO V",
                "item_number": "9999",
                "part": None,
                "label": "não existe",
            }
        ],
    )
    with pytest.raises(ContentError):
        load_pages(topics, paths, index)


def test_slug_must_be_url_safe(tmp_path, index):
    topics, paths = _dirs(tmp_path, id="Não Vale Assim")
    with pytest.raises(ContentError, match="slug"):
        load_pages(topics, paths, index)
