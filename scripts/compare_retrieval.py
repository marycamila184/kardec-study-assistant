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
from src.rag.retriever import REFLECT_BOOKS

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


REFLECT_CASES = [
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
            "DAS PENAS E GOZOS TERRESTRES",
        ],
        # The situation is low self-worth and sadness; DA LEI DO TRABALHO is
        # about the duty and purpose of labour. It matches on the word
        # "trabalho" alone — the near-miss this harness exists to measure.
        "avoid": ["DA LEI DO TRABALHO", "DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
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
        # The end of a marriage has no single facet — grief, forgiveness and
        # anxiety are all defensible readings. A label that pretends otherwise
        # measures the labeller. The avoid survives the ambiguity: marking a
        # chapter wrong does not require knowing which one is right.
        "expect": [
            "NÃO SEPAREIS O QUE DEUS JUNTOU",
            "BEM-AVENTURADOS OS AFLITOS",
            "DAS PENAS E GOZOS TERRESTRES",
            "AMAI OS VOSSOS INIMIGOS",
            "BEM‑AVENTURADOS OS QUE SÃO MISERICORDIOSOS",
        ],
        "avoid": ["DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
    },
    {
        # The verbatim phrasing that produced the failure this work exists for:
        # bge-m3 answered it with LE 340, a Spirit's agony before *reincarnating*.
        # Kept alongside ansiedade-futuro on purpose — the gap between the two
        # measures how much the ranking leans on query length.
        "id": "ansiedade-nua",
        "query": "estou me sentindo ansioso",
        "expect": [
            "BEM-AVENTURADOS OS AFLITOS",
            "A FÉ TRANSPORTA MONTANHAS",
            "DAS PENAS E GOZOS TERRESTRES",
        ],
        "avoid": ["DA VOLTA DO ESPÍRITO À VIDA CORPORAL"],
    },
]

CHAT_CASES = [
    {
        "id": "perispirito",
        "query": "O que é o perispírito e para que ele serve?",
        "expect": ["DOS ESPÍRITOS", "DA ENCARNAÇÃO DOS ESPÍRITOS", "OS FLUIDOS"],
        # The vital principle is not the perispirit: the beginner's confusion.
        "avoid": ["DO PRINCÍPIO VITAL"],
    },
    {
        "id": "por-que-reencarnamos",
        "query": "Por que reencarnamos? Qual o objetivo das vidas sucessivas?",
        "expect": [
            "DA PLURALIDADE DAS EXISTÊNCIAS",
            "CONSIDERAÇÕES SOBRE A PLURALIDADE DAS EXISTÊNCIAS",
            "DA VOLTA DO ESPÍRITO À VIDA CORPORAL",
            "NINGUÉM PODERÁ VER O REINO DE DEUS SE NÃO NASCER DE NOVO",
        ],
        # The original pair, now in the other direction.
        "avoid": ["DA VOLTA DO ESPÍRITO, EXTINTA A VIDA CORPÓREA, À VIDA ESPIRITUAL"],
    },
    {
        "id": "obsessao",
        "query": "O que é obsessão e como uma pessoa se liberta dela?",
        "expect": ["DA OBSESSÃO", "DOS INCONVENIENTES E PERIGOS DA MEDIUNIDADE"],
        # Same vocabulary of bad Spirits acting on people; the subject is the
        # refutation of the demon doctrine, not what to do about obsession.
        "avoid": ["OS DEMÔNIOS", "INTERVENÇÃO DOS DEMÔNIOS NAS MODERNAS MANIFESTAÇÕES"],
    },
    {
        "id": "quem-pode-ser-medium",
        "query": "Qualquer pessoa pode ser médium?",
        "expect": ["DOS MÉDIUNS", "DA FORMAÇÃO DOS MÉDIUNS", "DOS MÉDIUNS ESPECIAIS"],
        "avoid": ["DA MEDIUNIDADE NOS ANIMAIS"],
    },
    {
        "id": "para-que-serve-a-prece",
        "query": "Para que serve orar? A prece é atendida?",
        "expect": [
            "PEDI E OBTEREIS",
            "COLETÂNEA DE PRECES ESPÍRITAS",
            "DA LEI DE ADORAÇÃO",
        ],
        # Also addressing the spirit world, but a different act.
        "avoid": ["DAS EVOCAÇÕES"],
    },
    {
        "id": "milagres-do-evangelho",
        "query": "Como o Espiritismo explica os milagres do Evangelho?",
        "expect": ["CARACTERES DOS MILAGRES", "OS MILAGRES DO EVANGELHO", "OS FLUIDOS"],
        "avoid": [
            "HAVERÁ FALSOS CRISTOS E FALSOS PROFETAS",
            "DO CHARLATANISMO E DO EMBUSTE",
        ],
    },
    {
        "id": "penas-eternas",
        "query": "O inferno existe? As penas são eternas?",
        "expect": [
            "DOUTRINA DAS PENAS ETERNAS",
            "AS PENAS FUTURAS SEGUNDO O ESPIRITISMO",
            "O INFERNO",
            "DAS PENAS E GOZOS FUTUROS",
        ],
        # Near-identical title, opposite scope: this life, not the next.
        "avoid": ["DAS PENAS E GOZOS TERRESTRES"],
    },
    {
        "id": "fora-da-caridade",
        "query": 'O que quer dizer "fora da caridade não há salvação"?',
        "expect": [
            "FORA DA CARIDADE NÃO HÁ SALVAÇÃO",
            "DA LEI DE JUSTIÇA, DE AMOR E DE CARIDADE",
            "AMAR O PRÓXIMO COMO A SI MESMO",
        ],
        # Dense with charity vocabulary; the subject is ostentation in alms.
        "avoid": ["NÃO SAIBA A VOSSA MÃO ESQUERDA O QUE DÊ A VOSSA MÃO DIREITA"],
    },
]

CASE_SETS = [
    {
        "name": "reflexivo",
        # /reflect is restricted to these two works in production.
        "where": {"book": {"$in": list(REFLECT_BOOKS)}},
        "cases": REFLECT_CASES,
    },
    # /chat questions span all five works, so no filter.
    {"name": "chat", "where": None, "cases": CHAT_CASES},
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


def _index_corpus(collection: str, encoder) -> int:
    """Re-indexes the corpus into `collection` using `encoder(documents) ->
    vectors`. Reuses the production document builder so the only variable
    between lanes is the embedding model.

    A previous run may have died partway (the e5 lane's 512-token cap did
    exactly that). Half a corpus would silently skew every comparison, so any
    prior collection under this name is dropped before indexing starts.
    """
    import chromadb

    from src.ingestion.pipeline import BATCH_SIZE, _build_document, _build_id

    client = chromadb.PersistentClient(path=settings.chroma_path)
    try:
        client.delete_collection(collection)
        print(f"coleção {collection} anterior removida")
    except Exception:
        pass

    store = VectorStore(settings.chroma_path, collection)
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
                encoder(documents),
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
    return total


def index_e5() -> None:
    """Re-indexes the corpus into a second collection. Reuses the production
    document builder so the only variable is the embedding model."""
    total = _index_corpus(E5_COLLECTION, encode_e5)
    print(f"Indexado: {total} chunks em {E5_COLLECTION}")
    print(
        f"Truncados em {E5_MAX_CHARS} chars: {_truncated} "
        f"({_truncated / total * 100:.1f}%)"
    )


def index_gemini(dim: int) -> None:
    """Re-indexes the corpus with gemini-embedding-2 at `dim` dimensions.

    Reuses the production document builder so the only variable is the model.
    Nothing is truncated: a document the API refuses raises, because a silent
    cut is the failure mode this whole comparison exists to avoid.
    """
    collection = gemini_collection(dim)
    total = _index_corpus(collection, lambda docs: encode_gemini(docs, dim=dim))
    print(f"Indexado: {total} chunks em {collection}, 0 truncados")


# --- qwen lane ---------------------------------------------------------------

QWEN_MODEL = "qwen/qwen3-embedding-8b"
# 4096 is the native width; 1024 is the MRL truncation that matches bge-m3
# exactly, so that a win at 1024 is a win on model quality and not on having
# four times the room. 1024 is also the production candidate — at 7347 chunks
# the 4096 index is ~120 MB against ~30 MB, and that memory is paid on every
# cold start of a scale-to-zero instance.
QWEN_DIMS = (1024, 4096)
# Verified against the API: 100 is accepted. 64 matches the ingestion pipeline's
# BATCH_SIZE, so the lane sends exactly the batches production would.
QWEN_BATCH_MAX = 64

# Qwen3-Embedding is instruction-aware and ASYMMETRIC: the query carries a task
# instruction, the document carries none. This is the same trap documented for
# the e5 lane above — indexing documents with a prefix, or querying without one,
# degrades the model for a reason that has nothing to do with the model.
#
# One instruction serves both case sets on purpose. Tuning a separate prompt for
# `reflexivo` and for `chat` would make the lane's advantage partly a prompt
# result, and the question here is whether the *model* retrieves this corpus
# better. Per-mode instructions are a follow-up, not something this run measures.
QWEN_TASK = (
    "Given a question or a situation, retrieve passages from the Spiritist "
    "works of Allan Kardec that address it"
)


def qwen_query(text: str) -> str:
    return f"Instruct: {QWEN_TASK}\nQuery: {text}"


def qwen_collection(dim: int) -> str:
    return f"kardec_docs_qwen_{dim}"


def _openrouter_client():
    from openai import OpenAI

    key = settings.openrouter_api_key
    if not key:
        raise SystemExit("OPENROUTER_API_KEY não está no ambiente/.env")
    # max_retries covers the 429/5xx that a 115-batch corpus run will hit; the
    # SDK backs off exponentially and does NOT retry 4xx other than 429, so an
    # oversize document still fails loudly instead of being quietly dropped.
    return OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
        max_retries=6,
        timeout=120.0,
    )


def encode_qwen(
    texts: list[str], dim: int, is_query: bool = False
) -> list[list[float]]:
    """Embeds texts, no truncation anywhere by design.

    Qwen3-Embedding takes 32k tokens against a corpus p90 of 775 chars, so a
    document that does not fit is a broken assumption rather than an edge to
    absorb — the e5 lane's silent 1500-char cut is what this avoids.

    Results are reordered by the `index` the API returns rather than trusted to
    arrive in order. Nothing downstream would notice the difference: a shuffled
    batch stores every document against another document's vector, Chroma
    accepts it, and the only symptom is retrieval quietly getting worse.
    """
    client = _openrouter_client()
    payload = [qwen_query(t) for t in texts] if is_query else list(texts)
    vectors: list[list[float]] = []
    for start in range(0, len(payload), QWEN_BATCH_MAX):
        batch = payload[start : start + QWEN_BATCH_MAX]
        response = client.embeddings.create(
            model=QWEN_MODEL, input=batch, dimensions=dim
        )
        ordered = sorted(response.data, key=lambda d: d.index)
        if len(ordered) != len(batch):
            raise RuntimeError(
                f"a API devolveu {len(ordered)} vetores para {len(batch)} textos"
            )
        for d in ordered:
            if len(d.embedding) != dim:
                raise RuntimeError(
                    f"a API devolveu vetor de {len(d.embedding)} dims, esperado {dim}"
                )
        vectors.extend(d.embedding for d in ordered)
    return vectors


def index_qwen(dim: int) -> None:
    """Re-indexes the corpus with qwen3-embedding-8b at `dim` dimensions.

    Reuses the production document builder so the only variable is the model.
    Nothing is truncated: a document the API refuses raises, because a silent
    cut is the failure mode this whole comparison exists to avoid.
    """
    collection = qwen_collection(dim)
    total = _index_corpus(collection, lambda docs: encode_qwen(docs, dim=dim))
    print(f"Indexado: {total} chunks em {collection}, 0 truncados")


# --- querying ----------------------------------------------------------------


def top_bge(query: str, where: dict | None, k: int = 5) -> list[dict]:
    from src.ingestion.embeddings import encode

    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return store.query(encode([query])[0], n_results=k, where=where)


def top_e5(query: str, where: dict | None, k: int = 5) -> list[dict]:
    store = VectorStore(settings.chroma_path, E5_COLLECTION)
    return store.query(encode_e5([query], is_query=True)[0], n_results=k, where=where)


def top_gemini(query: str, where: dict | None, dim: int, k: int = 5) -> list[dict]:
    store = VectorStore(settings.chroma_path, gemini_collection(dim))
    return store.query(
        encode_gemini([query], dim=dim, is_query=True)[0], n_results=k, where=where
    )


def top_qwen(query: str, where: dict | None, dim: int, k: int = 5) -> list[dict]:
    store = VectorStore(settings.chroma_path, qwen_collection(dim))
    return store.query(
        encode_qwen([query], dim=dim, is_query=True)[0], n_results=k, where=where
    )


# Displayed name -> fn(query, where). Order and labels are contractual: they
# end up verbatim in the report the deployment decision cites.
LANES = {
    "bge-m3 (atual)": top_bge,
    "e5-instruct (Together)": top_e5,
    f"gemini-2 @{GEMINI_DIMS[0]}": lambda query, where: top_gemini(
        query, where, dim=GEMINI_DIMS[0]
    ),
    f"gemini-2 @{GEMINI_DIMS[1]}": lambda query, where: top_gemini(
        query, where, dim=GEMINI_DIMS[1]
    ),
    f"qwen3-8b @{QWEN_DIMS[0]}": lambda query, where: top_qwen(
        query, where, dim=QWEN_DIMS[0]
    ),
    f"qwen3-8b @{QWEN_DIMS[1]}": lambda query, where: top_qwen(
        query, where, dim=QWEN_DIMS[1]
    ),
}

# Lane -> the collection it reads. Single source of truth: the report uses it to
# skip lanes that were never indexed, and `_collection_counts` to size them.
LANE_COLLECTIONS = {
    "bge-m3 (atual)": settings.chroma_collection,
    "e5-instruct (Together)": E5_COLLECTION,
    f"gemini-2 @{GEMINI_DIMS[0]}": gemini_collection(GEMINI_DIMS[0]),
    f"gemini-2 @{GEMINI_DIMS[1]}": gemini_collection(GEMINI_DIMS[1]),
    f"qwen3-8b @{QWEN_DIMS[0]}": qwen_collection(QWEN_DIMS[0]),
    f"qwen3-8b @{QWEN_DIMS[1]}": qwen_collection(QWEN_DIMS[1]),
}


# --- scoring -----------------------------------------------------------------


def score(case: dict, hits: list[dict]) -> dict:
    """Rank of the first apt chapter, and whether a known-wrong one appeared.

    `best_rank` is 1-based; None means no apt chapter in the top k. Reported
    beside `avoid_hit` on purpose — a model that returns nothing apt and nothing
    wrong is not doing better than one that returns both.

    `top_distance` is the rank-1 hit's cosine distance, carried through so
    `summarize()` can compare it against production's cutoff — a raw top-5
    ranking win means nothing if `/reflect` or `/chat` would have discarded
    the hit as too far.
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
        "top_distance": hits[0]["distance"] if hits else None,
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    ranked = [r["best_rank"] for r in rows if r["best_rank"]]
    distances = [r["top_distance"] for r in rows if r["top_distance"] is not None]
    return {
        "n": n,
        "hit_rate@5": sum(1 for r in rows if r["hit"]) / n,
        "mean_best_rank": (sum(ranked) / len(ranked)) if ranked else None,
        "mrr": sum(1 / r["best_rank"] for r in rows if r["best_rank"]) / n,
        "avoid_hits": sum(1 for r in rows if r["avoid_hit"]),
        "dist@1": (round(sum(distances) / len(distances), 3) if distances else None),
        "over_cutoff": sum(1 for d in distances if d > settings.max_distance),
    }


def _collection_counts() -> dict[str, int | None]:
    """Document count per lane's collection, or None if it does not exist yet.

    A crashed --index run leaves a partial (or absent) collection that a
    ranking report cannot see on its own — the numbers still print, just
    against a corpus missing whole books. `VectorStore` has no count of its
    own, so the underlying chromadb client is read directly.
    """
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_path)
    counts: dict[str, int | None] = {}
    for lane, collection in LANE_COLLECTIONS.items():
        try:
            counts[lane] = client.get_collection(collection).count()
        except Exception:
            counts[lane] = None
    return counts


def report() -> None:
    counts = _collection_counts()
    print("# Documentos por coleção\n")
    for lane, count in counts.items():
        print(f"- {lane}: {count if count is not None else 'ausente'}")

    # A lane whose collection is absent or empty is SKIPPED, not queried.
    # `VectorStore` opens with get_or_create_collection, so querying an
    # un-indexed lane silently creates an empty collection and returns no hits —
    # which `score()` records as a real miss and `summarize()` prints as
    # `hit_rate@5: 0.0`. That number is indistinguishable from a model that
    # genuinely retrieved nothing, in a report whose only purpose is to decide a
    # production swap. Absent must read as absent.
    active = {name: fn for name, fn in LANES.items() if counts.get(name)}
    skipped = [name for name in LANES if not counts.get(name)]
    if skipped:
        print("\nVias não indexadas, fora da comparação: " + ", ".join(skipped))
    if not active:
        raise SystemExit("nenhuma via indexada — rode --index antes de --report")

    sizes = {counts[name] for name in active}
    if len(sizes) > 1:
        print(
            "\n⚠️  ATENÇÃO: as coleções indexadas não têm o mesmo número de "
            "documentos — uma reindexação pode ter parado no meio.\n"
        )

    for case_set in CASE_SETS:
        print(f"\n# Conjunto: {case_set['name']}\n")
        results: dict[str, list[dict]] = {name: [] for name in active}

        for case in case_set["cases"]:
            print(f"\n## [{case['id']}] {case['query']}\n")
            for name, fn in active.items():
                try:
                    hits = fn(case["query"], case_set["where"])
                except (Exception, SystemExit) as exc:
                    # A lane that is not indexed yet, or missing an API key
                    # (`_gemini_post`/`_together_client` raise SystemExit,
                    # which bare `except Exception` would not catch).
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
                        f"| item {m.get('item_number')} "
                        f"| dist {h['distance']:.3f}"
                    )
                print()

        print(f"\n## Resumo — {case_set['name']}\n")
        for name, rows in results.items():
            if rows:
                print(f"- {name}: {summarize(rows)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        choices=(
            ["e5"]
            + [f"gemini-{dim}" for dim in GEMINI_DIMS]
            + [f"qwen-{dim}" for dim in QWEN_DIMS]
        ),
        help="re-index the corpus with the given lane "
        "(one-off, ~US$0.25 for gemini, ~US$0.01 for qwen)",
    )
    parser.add_argument("--report", action="store_true", help="compare and print")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.index == "e5":
        index_e5()
    elif args.index and args.index.startswith("gemini-"):
        index_gemini(int(args.index.split("-")[1]))
    elif args.index and args.index.startswith("qwen-"):
        index_qwen(int(args.index.split("-")[1]))
    if args.report or not args.index:
        report()


if __name__ == "__main__":
    main()
