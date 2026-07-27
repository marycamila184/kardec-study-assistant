"""Does the hosted bge-m3 land in the same vector space as the indexed one?

The deployment plan is to stop loading 2.3 GB of `BAAI/bge-m3` in-process and
call the same model over HTTP instead. "The same model" is a claim about the
weights, not about the serving code: pooling (CLS vs mean), normalization, or
quantization can differ per provider and produce vectors from a different space.

That failure is silent. Chroma stores whatever vector it is handed, cosine
distance still returns a number, and retrieval simply gets worse — which is the
exact class of bug the 2026-07-26 retrieval evaluation existed to catch, and the
reason this script exists before the switch rather than after it.

Two questions, in order:

  1. Is the hosted vector the same vector? Compares hosted embeddings of already
     indexed documents against the vectors STORED for them. ~0.999 is parity.

  2. Does retrieval survive? The question that actually decides, because it is
     what a reader feels. Runs the same queries against the same index with the
     query encoded locally and hosted, comparing top-5 overlap and distances.

If 1 fails but 2 passes, the reading is: different space, internally consistent
— usable by REINDEXING (about US$0.011 for this corpus), never without.

Usage:
    uv run python -m scripts.verify_embedding_parity --provider deepinfra
"""

import argparse
import math
import random

from src.core.config import EMBEDDING_PROVIDERS, settings
from src.ingestion.vectorstore import VectorStore

# The reflect-era queries plus doctrinal ones: both vocabularies, because the
# retrieval evaluation showed a model can hold one register and lose the other.
QUERIES = [
    "o que é o perispírito?",
    "por que reencarnamos?",
    "o que a doutrina diz sobre o suicídio?",
    "estou me sentindo ansioso",
    "perdi alguém que eu amava",
    "qualquer pessoa pode ser médium?",
    "o inferno existe?",
    "o que quer dizer fora da caridade não há salvação?",
]


def _hit_id(hit: dict) -> tuple:
    m = hit["metadata"]
    return (
        m.get("book"),
        m.get("chapter_title"),
        m.get("item_number"),
        m.get("subchunk_index"),
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[idx]


def _encoders(provider: str):
    """Returns (local, hosted) encoders, each ignoring the global setting.

    Both must be callable in the same process and in either order, so neither
    can depend on `settings.embedding_provider` being set a particular way.
    """
    from src.ingestion import embeddings

    def local(texts: list[str]) -> list[list[float]]:
        return embeddings._get_model().encode(texts, convert_to_numpy=True).tolist()

    def hosted(texts: list[str]) -> list[list[float]]:
        previous = settings.embedding_provider
        settings.embedding_provider = provider
        try:
            return embeddings._encode_hosted(texts)
        finally:
            settings.embedding_provider = previous

    return local, hosted


def check_vector_parity(hosted, sample: int) -> bool:
    """Question 1: hosted vector vs the vector already in the index."""
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    collection = store._collection
    total = collection.count()
    print(f"\n## 1. Paridade de vetor ({sample} de {total} documentos)\n")

    # Deterministic sample: a parity check that moves between runs cannot be
    # compared against the previous run.
    random.seed(20260727)
    offset = random.randrange(max(1, total - sample))
    got = collection.get(
        limit=sample, offset=offset, include=["documents", "embeddings"]
    )
    documents = got["documents"]
    stored = got["embeddings"]

    hosted_vecs = hosted(documents)
    sims = [_cosine(h, s) for h, s in zip(hosted_vecs, stored)]

    dim_stored = len(stored[0])
    dim_hosted = len(hosted_vecs[0])
    print(f"  dimensões: índice {dim_stored}, hospedado {dim_hosted}")
    if dim_stored != dim_hosted:
        print("  ❌ dimensões diferentes — espaços incompatíveis, ponto final.")
        return False

    print(
        f"  cosseno: mín {min(sims):.6f} · p10 {_percentile(sims, 0.10):.6f} "
        f"· média {sum(sims) / len(sims):.6f} · máx {max(sims):.6f}"
    )
    if min(sims) >= 0.999:
        print("  ✅ paridade: mesmo espaço, índice atual continua válido.")
        return True
    if min(sims) >= 0.99:
        print("  ⚠️ quase: diferença pequena mas real; a pergunta 2 decide.")
        return False
    print("  ❌ espaço diferente — trocar sem reindexar degradaria o retrieval.")
    return False


def check_retrieval(local, hosted, k: int) -> None:
    """Question 2: same index, query encoded both ways — does the top-k move?"""
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    print(f"\n## 2. Retrieval sobre o mesmo índice (top-{k})\n")

    overlaps: list[float] = []
    shifts: list[float] = []
    for query in QUERIES:
        lv = local([query])[0]
        hv = hosted([query])[0]
        lhits = store.query(lv, n_results=k)
        hhits = store.query(hv, n_results=k)
        # VectorStore.query does not return ids; a hit is identified by the
        # chunk it points at, which is what "same result" means here anyway.
        lids = [_hit_id(h) for h in lhits]
        hids = [_hit_id(h) for h in hhits]
        overlap = len(set(lids) & set(hids)) / k
        overlaps.append(overlap)
        if lhits and hhits:
            shifts.append(abs(lhits[0]["distance"] - hhits[0]["distance"]))
        mark = "✅" if overlap == 1.0 else ("⚠️" if overlap >= 0.8 else "❌")
        same_order = "mesma ordem" if lids == hids else "ordem diferente"
        print(f"  {mark} [{overlap:.0%}] {same_order} — {query}")

    mean_overlap = sum(overlaps) / len(overlaps)
    print(
        f"\n  sobreposição média: {mean_overlap:.1%} · "
        f"desvio de distância no rank 1: {max(shifts):.4f} (máx)"
    )
    if mean_overlap == 1.0 and max(shifts) < 0.01:
        print("  ✅ trocar é seguro sem reindexar e sem recalibrar limiares.")
    elif mean_overlap >= 0.8:
        print("  ⚠️ o retrieval se move. Reindexar com a via hospedada e remedir.")
    else:
        print("  ❌ retrieval diferente — não trocar sem reindexar e recalibrar.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=sorted(EMBEDDING_PROVIDERS),
        required=True,
        help="hosted lane to verify against the local model",
    )
    parser.add_argument("--sample", type=int, default=40)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    local, hosted = _encoders(args.provider)
    print(f"# Paridade: {settings.embedding_model} local vs {args.provider}")
    check_vector_parity(hosted, args.sample)
    check_retrieval(local, hosted, args.k)


if __name__ == "__main__":
    main()
