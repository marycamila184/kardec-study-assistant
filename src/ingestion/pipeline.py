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
    """The chunk's identity in the store, and therefore what `upsert` collides on.

    `part` is in the key because Céu e Inferno restarts chapter *and* item
    numbering in each part: "CAPÍTULO I" item 1 is `O PORVIR E O NADA` in
    I PARTE and `O PASSAMENTO` in II PARTE. Without it the two share an id and
    the second overwrites the first — silently, since upsert treats it as an
    update. That cost 20 chunks of the production index (measured 2026-07-29).

    Omitted when empty rather than folded in as a blank field, so the books
    that carry no `part` (O Livro dos Espíritos, O Livro dos Médiuns) keep the
    ids they already have and a re-ingestion updates their rows instead of
    writing a second copy beside them.
    """
    chapter = (chunk.get("chapter") or "").replace(" ", "_").lower()
    part = (chunk.get("part") or "").replace(" ", "_").lower()
    prefix = f"{stem}_{part}" if part else stem
    return f"{prefix}_{chapter}_{chunk['item_number']}_{chunk['subchunk_index']}"


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
                    # Reassembly needs to know whether the cut before this
                    # piece was a paragraph break in the source or just the
                    # size limit. Defaults True for rows written before the
                    # field existed: a stale index then rejoins with "\n"
                    # rather than the old "\n\n", which is wrong in fewer
                    # places, but the field is only right after re-ingestion.
                    "starts_paragraph": c.get("starts_paragraph", True),
                }
                for c in batch
            ]
            store.upsert(ids, embeddings, documents, metadatas)

    print("Ingestion complete.")


if __name__ == "__main__":
    run_ingestion()
