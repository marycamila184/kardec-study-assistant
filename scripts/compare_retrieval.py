"""Compare embedding models by what they actually retrieve for this corpus.

The Reflexivo answers grief from LE 340 — the agony of a Spirit about to
*reincarnate* — because retrieval ranks by embedding proximity and that tracks
vocabulary, therefore affect. Asking the model to discard ill-fitting passages
was measured and rejected (see compare_reflect.py): it cannot judge aptness
better than the ranking can. So the fix has to be the ranking.

This script is also the deployment question in disguise. `BAAI/bge-m3` is 2.3 GB
loaded in-process, which forces an always-on Cloud Run instance (~US$90/month in
São Paulo). A hosted embedding API removes it, letting the service scale to
zero — but only if retrieval does not get worse. One experiment, two answers.

## The labels

Aptness is judged by chapter, not by hand-picking items: a chapter is a
coherent subject in these works, and the label survives re-chunking.

`expect` — chapters that genuinely address the situation.
`avoid`  — chapters that look apt to an embedding and are not. The pair that
           started this is in O Livro dos Espíritos and differs by two words:

             "DA VOLTA DO ESPÍRITO, EXTINTA A VIDA CORPÓREA, À VIDA ESPIRITUAL"
                 — death. What a grieving reader needs.
             "DA VOLTA DO ESPÍRITO À VIDA CORPORAL"
                 — rebirth. Where Q.340 lives.

           Nearly the same words, opposite subjects. An `avoid` hit is not a
           near miss; it is the failure being measured.

Usage:
    uv run python -m scripts.compare_retrieval --index e5   # one-off, ~US$0.03
    uv run python -m scripts.compare_retrieval --report
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request

from src.core.config import settings
from src.ingestion.vectorstore import VectorStore

E5_MODEL = "intfloat/multilingual-e5-large-instruct"
E5_COLLECTION = "kardec_docs_e5"

# multilingual-e5-large-instruct is asymmetric: the query carries a task
# instruction, the passage carries nothing. Indexing passages with a prefix, or
# querying without one, degrades the model badly — it would look worse than
# bge-m3 for a reason that has nothing to do with the model.
E5_TASK = (
    "Given a personal situation someone is living through, retrieve passages "
    "from the Spiritist works of Allan Kardec that speak to it"
)


def e5_query(text: str) -> str:
    return f"Instruct: {E5_TASK}\nQuery: {text}"


CASES = [
    {
        "id": "luto-alguem-amado",
        "query": "Perdi alguém que eu amava e estou sofrendo muito com essa perda.",
        "expect": [
            "BEM-AVENTURADOS OS AFLITOS",
            "O CRISTO CONSOLADOR",
            "COLETÂNEA DE PRECES ESPÍRITAS",
            "DA VOLTA DO ESPÍRITO, EXTINTA A VIDA CORPÓREA, À VIDA ESPIRITUAL",
            "DA VIDA ESPÍRITA",
        ],
        "avoid": ["DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
    },
    {
        "id": "luto-pai",
        "query": "perdi meu pai ano passado e ainda sinto uma saudade que não passa",
        "expect": [
            "BEM-AVENTURADOS OS AFLITOS",
            "O CRISTO CONSOLADOR",
            "COLETÂNEA DE PRECES ESPÍRITAS",
            "DA VOLTA DO ESPÍRITO, EXTINTA A VIDA CORPÓREA, À VIDA ESPIRITUAL",
            "DA VIDA ESPÍRITA",
        ],
        "avoid": ["DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
    },
    {
        "id": "perdao",
        "query": "não consigo perdoar quem me fez mal",
        "expect": [
            "AMAI OS VOSSOS INIMIGOS",
            "BEM‑AVENTURADOS OS QUE SÃO MISERICORDIOSOS",
            "DA LEI DE JUSTIÇA, DE AMOR E DE CARIDADE",
        ],
        "avoid": [],
    },
    {
        "id": "briga-mae",
        "query": "briguei com minha mãe e não sei como consertar",
        "expect": [
            "HONRAI A VOSSO PAI E A VOSSA MÃE",
            "AMAR O PRÓXIMO COMO A SI MESMO",
            "DA LEI DE SOCIEDADE",
        ],
        "avoid": [],
    },
    {
        "id": "inveja",
        "query": "tenho muita inveja de uma amiga e isso me envergonha",
        "expect": [
            "BEM-AVENTURADOS OS POBRES DE ESPÍRITO",
            "BEM-AVENTURADOS OS QUE TÊM PURO O CORAÇÃO",
            "DA PERFEIÇÃO MORAL",
        ],
        "avoid": [],
    },
    {
        "id": "trabalho-sem-valor",
        "query": "estou passando por uma fase muito difícil no trabalho e me sinto sem valor",
        "expect": [
            "BEM-AVENTURADOS OS AFLITOS",
            "BEM-AVENTURADOS OS POBRES DE ESPÍRITO",
            "DA LEI DO TRABALHO",
            "DAS PENAS E GOZOS TERRESTRES",
        ],
        "avoid": [],
    },
    {
        "id": "ansiedade-futuro",
        "query": "ando ansioso com o futuro e não consigo parar de me preocupar",
        "expect": [
            "BEM-AVENTURADOS OS AFLITOS",
            "A FÉ TRANSPORTA MONTANHAS",
            "DAS PENAS E GOZOS TERRESTRES",
        ],
        "avoid": ["DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
    },
    {
        "id": "separacao",
        "query": "meu casamento acabou e eu me sinto um fracasso",
        "expect": [
            "NÃO SEPAREIS O QUE DEUS JUNTOU",
            "BEM-AVENTURADOS OS AFLITOS",
            "DAS PENAS E GOZOS TERRESTRES",
        ],
        "avoid": [],
    },
]


# --- indexing ----------------------------------------------------------------


def _together_client():
    from openai import OpenAI

    key = settings.together_api_key
    if not key:
        raise SystemExit("TOGETHER_API_KEY não está no ambiente/.env")
    return OpenAI(api_key=key, base_url="https://api.together.xyz/v1")


# e5-large-instruct caps at 512 tokens, against bge-m3's 8192. Measured over the
# corpus, 38 of 7347 documents (0.5%) exceed it — median 564 chars, p90 775 — so
# this is an edge, not a wall. What overflows is almost always the footnote tail
# that _build_document appends, which exists for embedding only and is stripped
# on read. Budget is in characters because the API counts tokens and we cannot;
# ~3.3 chars/token in pt-BR, kept conservative.
E5_MAX_CHARS = 1500

_truncated = 0


def _fit(text: str) -> str:
    global _truncated
    if len(text) <= E5_MAX_CHARS:
        return text
    _truncated += 1
    return text[:E5_MAX_CHARS]


def encode_e5(texts: list[str], is_query: bool = False) -> list[list[float]]:
    client = _together_client()
    payload = [e5_query(t) for t in texts] if is_query else [_fit(t) for t in texts]
    response = client.embeddings.create(model=E5_MODEL, input=payload)
    return [d.embedding for d in response.data]


# --- gemini lane -------------------------------------------------------------

GEMINI_MODEL = "gemini-embedding-2"
GEMINI_DIMS = (1024, 3072)
# The API rejects a larger batch outright with 400 INVALID_ARGUMENT.
GEMINI_BATCH_MAX = 100
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:batchEmbedContents"
)
# 429 is expected during a full-corpus run (74 batches) and must not end it.
GEMINI_RETRY_STATUSES = (429, 500, 502, 503, 504)


def gemini_collection(dim: int) -> str:
    return f"kardec_docs_gemini_{dim}"


class GeminiHTTPError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def _gemini_post(body: dict) -> dict:
    """One HTTP call. This is the seam the tests replace — they never touch
    urllib, so a change of transport does not invalidate them."""
    key = settings.google_api_key
    if not key:
        raise SystemExit("GOOGLE_API_KEY não está no ambiente/.env")
    request = urllib.request.Request(
        GEMINI_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise GeminiHTTPError(exc.code, exc.read().decode("utf-8", "replace")) from exc


def _post_with_retry(body: dict, attempts: int = 6, sleep=time.sleep) -> dict:
    """Retries only what a retry can fix. A 400 is the oversize-document
    signal and propagates immediately: the corpus fits in 8192 tokens, so a
    rejection means an assumption broke and the run must stop, not shrink."""
    for attempt in range(attempts):
        try:
            return _gemini_post(body)
        except GeminiHTTPError as exc:
            if exc.status not in GEMINI_RETRY_STATUSES or attempt == attempts - 1:
                raise
            sleep(2**attempt)
    raise AssertionError("unreachable")


def encode_gemini(
    texts: list[str], dim: int, is_query: bool = False
) -> list[list[float]]:
    """Embeds texts, no truncation anywhere by design.

    gemini-embedding-2 takes 8192 tokens against a corpus p90 of 775 chars, so
    a document that does not fit is a broken assumption rather than an edge to
    absorb — the e5 lane's silent 1500-char cut is what this avoids.
    """
    task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    vectors: list[list[float]] = []
    for start in range(0, len(texts), GEMINI_BATCH_MAX):
        batch = texts[start : start + GEMINI_BATCH_MAX]
        data = _post_with_retry(
            {
                "requests": [
                    {
                        "model": f"models/{GEMINI_MODEL}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": task_type,
                        "outputDimensionality": dim,
                    }
                    for text in batch
                ]
            }
        )
        returned = [e["values"] for e in data.get("embeddings", [])]
        if len(returned) != len(batch):
            raise RuntimeError(
                f"a API devolveu {len(returned)} vetores para {len(batch)} textos"
            )
        vectors.extend(returned)
    return vectors


def index_e5() -> None:
    """Re-indexes the corpus into a second collection. Reuses the production
    document builder so the only variable is the embedding model."""
    import chromadb

    from src.ingestion.pipeline import BATCH_SIZE, _build_document, _build_id

    # A previous run may have died partway (the 512-token cap did exactly
    # that). Half a corpus would silently skew every comparison.
    client = chromadb.PersistentClient(path=settings.chroma_path)
    try:
        client.delete_collection(E5_COLLECTION)
        print(f"coleção {E5_COLLECTION} anterior removida")
    except Exception:
        pass

    store = VectorStore(settings.chroma_path, E5_COLLECTION)
    total = 0
    for filename in sorted(os.listdir(settings.json_dir)):
        if not filename.endswith(".json"):
            continue
        stem = filename[:-5]
        with open(os.path.join(settings.json_dir, filename), encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"  {stem}: {len(chunks)} chunks")
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            documents = [_build_document(c) for c in batch]
            store.upsert(
                [_build_id(stem, c) for c in batch],
                encode_e5(documents),
                documents,
                [
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
                ],
            )
            total += len(batch)
    print(f"Indexado: {total} chunks em {E5_COLLECTION}")
    print(
        f"Truncados em {E5_MAX_CHARS} chars: {_truncated} "
        f"({_truncated / total * 100:.1f}%)"
    )


# --- querying ----------------------------------------------------------------

REFLECT_BOOKS = ("O Livro dos Espíritos", "O Evangelho Segundo o Espiritismo")


def _where():
    return {"book": {"$in": list(REFLECT_BOOKS)}}


def top_bge(query: str, k: int = 5) -> list[dict]:
    from src.ingestion.embeddings import encode

    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return store.query(encode([query])[0], n_results=k, where=_where())


def top_e5(query: str, k: int = 5) -> list[dict]:
    store = VectorStore(settings.chroma_path, E5_COLLECTION)
    return store.query(
        encode_e5([query], is_query=True)[0], n_results=k, where=_where()
    )


# --- scoring -----------------------------------------------------------------


def score(case: dict, hits: list[dict]) -> dict:
    """Rank of the first apt chapter, and whether a known-wrong one appeared.

    `best_rank` is 1-based; None means no apt chapter in the top k. Reported
    beside `avoid_hit` on purpose — a model that returns nothing apt and nothing
    wrong is not doing better than one that returns both.
    """
    titles = [h["metadata"].get("chapter_title", "") for h in hits]
    best = next(
        (i + 1 for i, t in enumerate(titles) if t in case["expect"]),
        None,
    )
    return {
        "best_rank": best,
        "hit": best is not None,
        "avoid_hit": any(t in case["avoid"] for t in titles),
        "titles": titles,
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    ranked = [r["best_rank"] for r in rows if r["best_rank"]]
    return {
        "hit_rate@5": sum(1 for r in rows if r["hit"]) / n,
        "mean_best_rank": (sum(ranked) / len(ranked)) if ranked else None,
        "mrr": sum(1 / r["best_rank"] for r in rows if r["best_rank"]) / n,
        "avoid_hits": sum(1 for r in rows if r["avoid_hit"]),
    }


def report() -> None:
    lanes = {"bge-m3 (atual)": top_bge, "e5-instruct (Together)": top_e5}
    results: dict[str, list[dict]] = {name: [] for name in lanes}

    for case in CASES:
        print(f"\n## [{case['id']}] {case['query']}\n")
        for name, fn in lanes.items():
            try:
                hits = fn(case["query"])
            except Exception as exc:  # a lane that is not indexed yet
                print(f"### {name}\n\n  (indisponível: {exc})\n")
                continue
            s = score(case, hits)
            results[name].append(s)
            print(
                f"### {name} — rank do apto: {s['best_rank'] or '—'}"
                f"{'  ⚠️ trouxe capítulo errado' if s['avoid_hit'] else ''}\n"
            )
            for i, h in enumerate(hits, 1):
                m = h["metadata"]
                mark = (
                    "✅"
                    if m.get("chapter_title") in case["expect"]
                    else "❌" if m.get("chapter_title") in case["avoid"] else "  "
                )
                print(
                    f"  {mark} {i}. {m['book']} | {m.get('chapter_title')} "
                    f"| item {m.get('item_number')}"
                )
            print()

    print("\n## Resumo\n")
    for name, rows in results.items():
        if rows:
            print(f"- {name}: {summarize(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        choices=["e5"],
        help="re-index the corpus with the given model (one-off, ~US$0.03)",
    )
    parser.add_argument("--report", action="store_true", help="compare and print")
    args = parser.parse_args()

    if args.index == "e5":
        index_e5()
    if args.report or not args.index:
        report()


if __name__ == "__main__":
    main()
