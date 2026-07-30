import json
import os

import pytest

from src.ingestion.embeddings import encode
from src.ingestion.pipeline import _build_id, run_ingestion
from src.ingestion.vectorstore import VectorStore

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_chunks.json")


@pytest.fixture
def tmp_json_dir(tmp_path):
    json_dir = tmp_path / "json_files"
    json_dir.mkdir()
    with open(FIXTURE, encoding="utf-8") as f:
        chunks = json.load(f)
    with open(json_dir / "livro-espiritos.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    return str(json_dir)


def test_pipeline_ingests_all_chunks(tmp_json_dir, tmp_path, monkeypatch):
    chroma_dir = str(tmp_path / "embeddings")
    monkeypatch.setattr("src.ingestion.pipeline.settings.json_dir", tmp_json_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_path", chroma_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_collection", "col1")

    run_ingestion()

    store = VectorStore(chroma_dir, "col1")
    results = store.query(encode(["encarnação"])[0], n_results=5)
    assert len(results) == 2


def test_pipeline_appends_footnotes_to_document(tmp_json_dir, tmp_path, monkeypatch):
    chroma_dir = str(tmp_path / "embeddings2")
    monkeypatch.setattr("src.ingestion.pipeline.settings.json_dir", tmp_json_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_path", chroma_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_collection", "col2")

    run_ingestion()

    store = VectorStore(chroma_dir, "col2")
    results = store.query(encode(["encarnação"])[0], n_results=5)
    chunk_132 = next(r for r in results if r["metadata"]["item_number"] == "132")
    assert "[Nota 1]" in chunk_132["content"]


def test_pipeline_appends_title_footnotes_to_document(
    tmp_json_dir, tmp_path, monkeypatch
):
    chroma_dir = str(tmp_path / "embeddings3")
    monkeypatch.setattr("src.ingestion.pipeline.settings.json_dir", tmp_json_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_path", chroma_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_collection", "col3")

    run_ingestion()

    store = VectorStore(chroma_dir, "col3")
    results = store.query(encode(["encarnação"])[0], n_results=5)
    chunk_132 = next(r for r in results if r["metadata"]["item_number"] == "132")
    assert "[Nota 2]" in chunk_132["content"]  # title_footnote number 2 from fixture


def test_build_id_separates_chapters_that_repeat_across_parts():
    """Céu e Inferno numbers chapters per part: "CAPÍTULO I" exists in both
    I PARTE ("O PORVIR E O NADA") and II PARTE ("O PASSAMENTO"), each with its
    own item 1. An id built without `part` collides, and `upsert` resolves a
    collision by overwriting — so the second passage silently replaces the
    first and becomes unreachable by retrieval. Measured 2026-07-29 against the
    real corpus: 20 chunks were missing from the production index this way.
    """
    porvir = {
        "part": "I PARTE",
        "chapter": "CAPÍTULO I",
        "chapter_title": "O PORVIR E O NADA",
        "item_number": 1,
        "subchunk_index": 1,
    }
    passamento = {**porvir, "part": "II PARTE", "chapter_title": "O PASSAMENTO"}

    assert _build_id("ceu-inferno", porvir) != _build_id("ceu-inferno", passamento)


def test_build_id_is_stable_for_chunks_without_a_part():
    """`part` is folded in only when present. O Evangelho and A Gênese carry
    none, so their ids must stay byte-for-byte what they were — a re-ingestion
    has to update those rows, not write a second copy beside them.

    The three books that do carry a part (Céu e Inferno, O Livro dos Espíritos,
    O Livro dos Médiuns) get new ids by design, which is why the index must be
    rebuilt from empty rather than re-ingested over.
    """
    chunk = {
        "part": "",
        "chapter": "CAPÍTULO I",
        "item_number": 132,
        "subchunk_index": 1,
    }

    assert _build_id("evangelho", chunk) == "evangelho_capítulo_i_132_1"


def test_pipeline_stores_subsection_in_metadata(tmp_json_dir, tmp_path, monkeypatch):
    chroma_dir = str(tmp_path / "embeddings4")
    monkeypatch.setattr("src.ingestion.pipeline.settings.json_dir", tmp_json_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_path", chroma_dir)
    monkeypatch.setattr("src.ingestion.pipeline.settings.chroma_collection", "col4")

    run_ingestion()

    store = VectorStore(chroma_dir, "col4")
    results = store.query(encode(["encarnação"])[0], n_results=5)
    chunk_133 = next(r for r in results if r["metadata"]["item_number"] == "133")
    assert chunk_133["metadata"]["subsection"] == "Uma subseção"
