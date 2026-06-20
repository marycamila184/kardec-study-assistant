import json
import os

import pytest

from src.ingestion.embeddings import encode
from src.ingestion.pipeline import run_ingestion
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
