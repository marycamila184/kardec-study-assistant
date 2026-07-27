"""Builds the index that ships, containing only the collection that answers.

`data/embeddings/` on a development machine accumulates evaluation collections —
`kardec_docs_e5`, `kardec_docs_gemini_1024`, `kardec_docs_gemini_3072` — which
are three of its four directories and most of its 324 MB. None of them belongs
in a container image that gets pulled on every cold start.

Deleting them in place does not work: SQLite does not return freed pages to the
filesystem without a VACUUM, so `chroma.sqlite3` stays large and the image stays
fat. This writes a fresh directory instead, and the old one is left untouched so
a failed run costs nothing.

Nothing is re-embedded. The vectors already exist and are copied verbatim, which
makes this free, exact, and impossible to get wrong in the way a re-index could
(a different model, a different pooling, a silently different vector space).

Usage:
    uv run python -m scripts.build_production_index
    uv run python -m scripts.build_production_index --out data/embeddings-prod
"""

import argparse
import os

import chromadb

from src.core.config import settings

# Chroma reads a whole page of rows into memory per call; the corpus is small
# but there is no reason to hold 7327 × 1024 floats at once.
COPY_BATCH = 500


def build(source_path: str, out_path: str, collection_name: str) -> None:
    if os.path.exists(out_path):
        raise SystemExit(
            f"{out_path} já existe — apague ou passe outro --out. "
            "Este script nunca sobrescreve um índice existente."
        )

    source = chromadb.PersistentClient(path=source_path).get_collection(collection_name)
    total = source.count()
    print(f"origem: {collection_name} em {source_path} ({total} documentos)")

    target_client = chromadb.PersistentClient(path=out_path)
    target = target_client.get_or_create_collection(
        collection_name,
        # Must match the source: the distance metric is a property of the index,
        # and the thresholds in config.py (max_distance 0.55) were calibrated
        # against cosine. Creating this with the default L2 would silently
        # change every distance the app compares.
        metadata={"hnsw:space": "cosine"},
    )

    copied = 0
    for offset in range(0, total, COPY_BATCH):
        got = source.get(
            limit=COPY_BATCH,
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )
        target.add(
            ids=got["ids"],
            embeddings=got["embeddings"],
            documents=got["documents"],
            metadatas=got["metadatas"],
        )
        copied += len(got["ids"])
        print(f"  {copied}/{total}")

    if target.count() != total:
        raise SystemExit(
            f"copiados {target.count()} de {total} — índice incompleto, não use"
        )

    size = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(out_path)
        for f in files
    )
    print(f"\n✅ {out_path}: {target.count()} documentos, {size / 1e6:.0f} MB")
    print("   (origem intacta; nada foi apagado)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=settings.chroma_path)
    parser.add_argument("--out", default="data/embeddings-prod")
    parser.add_argument("--collection", default=settings.chroma_collection)
    args = parser.parse_args()

    build(args.source, args.out, args.collection)


if __name__ == "__main__":
    main()
