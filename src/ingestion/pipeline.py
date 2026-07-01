import json
import os

from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

BATCH_SIZE = 64
MAX_DOCUMENT_CHARS = 3000


def _build_document(chunk: dict) -> str:
    doc = chunk["content"]
    for note in chunk.get("title_footnotes", []) + chunk.get("footnotes", []):
        candidate = f"\n[Nota {note['number']}] {note['content']}"
        if len(doc) + len(candidate) <= MAX_DOCUMENT_CHARS:
            doc += candidate
    return doc


def _build_id(stem: str, chunk: dict) -> str:
    chapter = (chunk.get("chapter") or "").replace(" ", "_").lower()
    return f"{stem}_{chapter}_{chunk['item_number']}_{chunk['subchunk_index']}"


def run_ingestion() -> None:
    store = VectorStore(settings.chroma_path, settings.chroma_collection)

    for filename in os.listdir(settings.json_dir):
        if not filename.endswith(".json"):
            continue
        stem = filename[:-5]
        path = os.path.join(settings.json_dir, filename)

        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)

        print(f"Ingesting {stem} ({len(chunks)} chunks)…")

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            documents = [_build_document(c) for c in batch]
            embeddings = encode(documents)
            ids = [_build_id(stem, c) for c in batch]
            metadatas = [
                {
                    "book": c["book"],
                    "part": c.get("part") or "",
                    "chapter": c.get("chapter") or "",
                    "chapter_title": c.get("chapter_title") or "",
                    "subsection": c.get("subsection") or "",
                    "item_number": str(c["item_number"]),
                    "subchunk_index": c["subchunk_index"],
                    "total_subchunks": c["total_subchunks"],
                }
                for c in batch
            ]
            store.upsert(ids, embeddings, documents, metadatas)

    print("Ingestion complete.")


if __name__ == "__main__":
    run_ingestion()
