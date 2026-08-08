import re

import pytest

from src.discovery.corpus import (
    AmbiguousPassage,
    PassageNotFound,
    load_corpus,
    passage_text,
)

# data/json_files/ is gitignored and regenerable, so the unit tests read a
# committed fixture carved out of it. It holds exactly the shapes under test:
# a single-subchunk item, the Céu e Inferno key that collides across parts,
# a chunk with real footnotes, and a 15-subchunk item whose seams include
# mid-paragraph splits.
JSON_DIR = "tests/fixtures/discovery_corpus"


@pytest.fixture(scope="module")
def index():
    return load_corpus(JSON_DIR)


def test_joins_a_single_subchunk_item(index):
    text = passage_text(index, "O Evangelho Segundo o Espiritismo", "CAPÍTULO V", "1")
    assert text
    assert "\n\n" not in text  # join_subchunks never emits a blank line


def test_a_mid_paragraph_seam_rejoins_with_the_space_the_split_consumed(index):
    # The seam `starts_paragraph=False` marks: a paragraph cut only because it
    # was over max_chars. Rejoining it with nothing glues the two words
    # together ("dissipá-las?Seu objetivo"), which reads as a typo forever in a
    # page served for years. A test asserting only "no blank line" passes
    # against that bug — this one does not.
    text = passage_text(index, "O Livro dos Médiuns", None, "section-2")
    assert "\n\n" not in text
    # The seam itself: the piece before ends "...dissipá-las?" and the piece
    # after starts "Seu objetivo...". They must not touch.
    assert ". Seu objetivo consiste" in text
    # And nowhere may a sentence-ending period touch the next capital, which
    # is exactly what a swallowed separator produces.
    assert not re.search(r"[a-zà-úç]\.[A-ZÀ-Ú]", text)


def test_ceu_e_inferno_needs_the_part_to_disambiguate(index):
    # CAPÍTULO I item 1 exists in both parts: O PORVIR E O NADA (I PARTE,
    # two subchunks) and O PASSAMENTO (II PARTE, one).
    porvir = passage_text(index, "O Céu e o Inferno", "CAPÍTULO I", "1", part="I PARTE")
    passamento = passage_text(
        index, "O Céu e o Inferno", "CAPÍTULO I", "1", part="II PARTE"
    )
    assert porvir and passamento
    assert porvir != passamento


def test_omitting_a_required_part_raises_rather_than_gluing(index):
    # The 2026-08-03 bug in static form. Silence here would be permanent.
    with pytest.raises(AmbiguousPassage):
        passage_text(index, "O Céu e o Inferno", "CAPÍTULO I", "1")


def test_missing_passage_raises(index):
    with pytest.raises(PassageNotFound):
        passage_text(index, "O Evangelho Segundo o Espiritismo", "CAPÍTULO V", "9999")


def test_footnotes_are_not_appended(index):
    # Footnotes are baked in by ingestion's _build_document, never here.
    for chunks in index.values():
        for chunk in chunks:
            if chunk.get("footnotes"):
                assert "[Nota " not in chunk["content"]
                break
