# Design: Ingestion, RAG, and API Layers

**Date:** 2026-06-20
**Status:** Implemented
**Scope:** Implement `src/ingestion/`, `src/rag/`, and `src/api/` — the three empty scaffolds remaining after the parsing layer is complete.

## Implementation Notes (deviations from original spec)

- **LLM:** switched from Anthropic SDK (`claude-haiku-4-5`) to Groq API (OpenAI-compatible endpoint, `llama-3.1-8b-instant`). `.env` key is `GROQ_API_KEY`, not `ANTHROPIC_API_KEY`. The interface is otherwise identical.
- **`VectorStore`:** gained a `get_by_filter(where: dict) -> list[dict]` method (uses ChromaDB `.get()` not `.query()`) for metadata-only lookups without embedding. Used by `/study` (item lookup) and `/evangelho` (book filter).
- **`_build_document`:** footnotes are appended after content but capped at 2000 chars total. Very long footnotes (e.g. item 188 in Livro dos Espíritos, ~3600 chars combined) would otherwise exceed the embedding model's context window. Full footnote text remains in the JSON metadata.
- **`ChatResponse`:** gained `suggested_mode: str | None` field populated by regex-based intent detection (no LLM cost) in `src/rag/mode_detector.py`.
- **Additional endpoints beyond original scope:** `/study`, `/reflect`, `/evangelho`, `/paths`, `/paths/{path_id}` were added in subsequent feature sprints. See their own spec files.

---

## 1. Context

The parsing pipeline (`src/parsing/`) is fully implemented and produces structured JSON chunks from Kardec's five books. Each chunk has these fields:

```json
{
  "book": "O Livro dos Espíritos",
  "part": "SEGUNDA PARTE — O MUNDO ESPÍRITA",
  "chapter": "CAPÍTULO I",
  "chapter_title": "Da Encarnação dos Espíritos",
  "subsection": null,
  "item_number": "132",
  "subchunk_index": 1,
  "total_subchunks": 1,
  "content": "...",
  "footnotes": [{ "number": "1", "content": "..." }],
  "title_footnotes": []
}
```

`footnotes` contains only the footnotes whose `___…___` block appears immediately after this specific paragraph — footnotes are per-paragraph, not per-section. `title_footnotes` contains footnotes whose block appears immediately after the heading (`chapter_title` or `subsection`) under which this chunk lives; it is carried identically on every chunk under that heading.

These JSON files are the input contract for this design. We do not touch the parsing layer.

---

## 2. Stack

| Component | Library |
|---|---|
| Embeddings | `sentence-transformers` — `paraphrase-multilingual-mpnet-base-v2` (local, free, handles Portuguese) |
| Vector store | `chromadb` (local persistent) |
| LLM | `anthropic` SDK — `claude-haiku-4-5` for both generation and query condensation |
| API | `fastapi` + `uvicorn` |
| Config | `pydantic-settings` reading from `.env` |

---

## 3. Config (`src/core/config.py`)

Single `Settings` object loaded once at startup via `pydantic-settings`. All tunables live here.

```python
ANTHROPIC_API_KEY: str        # from .env
EMBEDDING_MODEL: str = "paraphrase-multilingual-mpnet-base-v2"
CHAT_MODEL: str = "claude-haiku-4-5"
CONDENSER_MODEL: str = "claude-haiku-4-5"
TOP_K: int = 5
MAX_DISTANCE: float = 1.2     # cosine distance threshold — chunks above this are discarded
MAX_HISTORY_TURNS: int = 10
CHROMA_PATH: str = "data/embeddings/"
CHROMA_COLLECTION: str = "kardec_docs"
JSON_DIR: str = "data/json_files"
```

`.env` only needs one key: `ANTHROPIC_API_KEY`.

---

## 4. Ingestion Layer (`src/ingestion/`)

**Purpose:** run once (or re-run to rebuild) to embed all parsed JSON chunks and persist them in ChromaDB.

### 4.1 `embeddings.py`

Wraps `SentenceTransformer`. Loaded once as a module-level singleton to avoid reloading the model on every call.

```
EmbeddingModel
  encode(texts: list[str]) -> list[list[float]]
```

### 4.2 `vectorstore.py`

Wraps the ChromaDB client. Creates or opens the persistent collection.

```
VectorStore
  __init__(path, collection_name)
  upsert(ids, embeddings, documents, metadatas)
  query(embedding, n_results) -> list[dict]
    returns: list of {"content": str, "metadata": dict, "distance": float}
```

Metadata stored per chunk: `book`, `part`, `chapter`, `chapter_title`, `subsection`, `item_number`, `subchunk_index`, `total_subchunks`.

The **document string** stored in ChromaDB (and returned to the prompt) is `content` + all footnote text concatenated — both `footnotes` (paragraph-level) and `title_footnotes` (heading-level) — so all of Kardec's notes are searchable and visible to the model. Both are serialised as `"\n[Nota N] <text>"` and appended at ingestion time.

Document ID format: `{book_filename_stem}_{item_number}_{subchunk_index}` (e.g. `livro-espiritos_132_1`) — stable across re-runs, making upsert idempotent.

### 4.3 `pipeline.py`

Orchestrates ingestion: loads JSON → batches → embeds → upserts.

```
run_ingestion()
  for each *.json in JSON_DIR:
    load chunks
    embed chunk["content"] in batches of 64
    upsert to VectorStore
```

Run via: `uv run python -m src.ingestion.pipeline`

---

## 5. RAG Layer (`src/rag/`)

Handles the full request cycle: query condensation → retrieval → prompt construction → generation.

### 5.1 `retriever.py`

```
retrieve(query: str, top_k: int) -> list[dict]
  embed query with EmbeddingModel
  query VectorStore for top_k results
  discard any result with distance > MAX_DISTANCE
  return remaining chunks with content + metadata
```

The distance filter is what triggers the out-of-doctrine path (see Section 5.4). ChromaDB uses cosine distance (range 0–2); `MAX_DISTANCE = 1.2` corresponds roughly to cosine similarity < 0.4, meaning the query has little semantic overlap with anything in the corpus.

### 5.2 `prompt.py`

Builds the system prompt and the user message passed to Claude.

**System prompt structure:**

```
You are a study assistant for the Spiritist doctrine, grounded exclusively
in Allan Kardec's five foundational works. Answer only from the retrieved
passages below. If the passages do not contain enough information to answer,
say so explicitly — do not invent doctrine.

Respond in Portuguese (Brazil). Clearly separate what comes from the source
text and what is your explanation.

[RETRIEVED PASSAGES]
[1] Book: O Livro dos Espíritos | Chapter: ... | Item: 132
    "..."
[2] ...
```

**Exposed function:**

```
build_messages(question: str, chunks: list[dict], history: list[dict]) -> list[dict]
  returns the full messages list ready for anthropic.messages.create()
```

History turns are prepended as `{"role": "user"/"assistant", "content": "..."}` before the current question, capped at `MAX_HISTORY_TURNS`.

### 5.3 `generator.py`

Two responsibilities:

**Query condensation** (only when `history` is non-empty):

```
condense_query(question: str, history: list[dict]) -> str
```

Calls `claude-haiku-4-5` with a short prompt:
> "Given this conversation history, rewrite the latest question as a fully self-contained search query. Return only the rewritten query."

This turns "O que ele disse sobre isso?" into a proper standalone query for embedding.

**Answer generation:**

```
generate(question: str, history: list[dict]) -> dict
  condensed = condense_query(question, history) if history else question
  chunks = retrieve(condensed, TOP_K)
  messages = build_messages(question, chunks, history)  # original question for display
  response = anthropic.messages.create(model=CHAT_MODEL, messages=messages)
  sources = deduplicated list of {book, chapter, item_number} from chunks
  return {"answer": response.content[0].text, "sources": sources}
```

No streaming for the PoC. Streaming can be added later by changing the `create()` call.

### 5.4 Out-of-Doctrine Handling

When a user asks something with no grounding in Kardec's works (e.g., questions about other religions, general philosophy, or topics simply not covered), the system must not hallucinate doctrine. There are two layers of protection:

**Layer 1 — Distance filter (hard gate, no Claude call):**

If `retriever.retrieve()` returns an empty list after filtering, `generator.generate()` short-circuits immediately — Claude is never called. The response is a fixed Portuguese message:

> *"Não encontrei nas obras de Kardec informações suficientes para responder a essa pergunta. Por favor, reformule sua dúvida ou consulte diretamente as obras."*

The `ChatResponse` in this case has `sources: []` and `not_found: true`. This saves API cost and avoids any chance of Claude improvising.

**Layer 2 — System prompt instruction (soft gate, Claude handles it):**

When some chunks are retrieved but their content is only marginally relevant, the system prompt explicitly instructs Claude:

> *"If the passages do not contain enough information to answer, say so explicitly — do not invent doctrine."*

Claude will respond in Portuguese that it cannot find a sufficient answer, and may suggest rephrasing or pointing to a specific book.

**What triggers the out-of-doctrine path:**

| Scenario | Distance result | Path |
|---|---|---|
| Clear doctrine question (reencarnação, médiuns, etc.) | Low (< 0.8) | Normal generation |
| Tangentially related question | Medium (0.8–1.2) | Generation with marginal chunks; Claude soft-gates if needed |
| Completely off-topic question | High (> 1.2) | All chunks discarded → hard gate → fixed "not found" message |

The `MAX_DISTANCE` threshold (default 1.2) is tunable in config and may need adjustment after testing on real queries.

---

## 6. API Layer (`src/api/`)

### 6.1 `schemas.py`

```python
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    question: str
    history: list[Message] = []

class Source(BaseModel):
    book: str
    chapter: str | None
    item_number: str | None

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    not_found: bool = False   # True when no chunks passed the distance threshold
```

No session_id — the client owns conversation history. The API is stateless.

### 6.2 `routes.py`

```
POST /chat
  body: ChatRequest
  calls generator.generate(question, history)
  returns: ChatResponse

GET /health
  returns: {"status": "ok"}
```

### 6.3 `main.py`

```python
app = FastAPI(title="Dialogando com a Doutrina")
app.include_router(router)
```

Run via: `uv run uvicorn src.api.main:app --reload`

---

## 7. End-to-End Data Flow

```mermaid
flowchart TD
    A([Client\nPOST /chat]) --> B{Has history?}

    B -- yes --> C[condenser\nclaude-haiku-4-5]
    C --> D[condensed_query]
    B -- no --> D[original question]

    D --> E[EmbeddingModel.encode]
    E --> F[VectorStore.query\ntop K results]
    F --> G{All distances\n> MAX_DISTANCE?}

    G -- yes --> H[/"Não encontrei nas obras\nde Kardec informações\nsuficientes…"/]
    H --> I([ChatResponse\nanswer, sources=[], not_found=true])

    G -- no --> J[prompt.build_messages\noriginal question + chunks + history]
    J --> K[claude-haiku-4-5\ngenerate answer]
    K --> L([ChatResponse\nanswer, sources, not_found=false])
```

---

## 8. Error Handling

- **Out-of-doctrine question**: handled by the two-layer system in Section 5.4 — no special error path needed.
- **Anthropic API error**: let FastAPI's default 500 propagate for the PoC. No retry logic.
- **Missing JSON files** (ingestion not run): ingestion pipeline prints a warning and skips; ChromaDB collection will be empty, which triggers the out-of-doctrine hard gate for every query.

---

## 9. Updated `pyproject.toml` Dependencies

```toml
dependencies = [
    "anthropic>=0.20.0",
    "sentence-transformers>=2.7.0",
    "chromadb>=0.4.0",
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv",
]
```

Remove `openai` and `tiktoken`.

---

## 10. Testing Approach

- **`tests/test_ingestion.py`** — load a small fixture JSON (2–3 chunks), run `run_ingestion()` against a temp Chroma path, assert chunks are queryable.
- **`tests/test_retriever.py`** — query the same temp store, assert top result is relevant by checking metadata fields.
- **`tests/test_prompt.py`** — unit test `build_messages()` with mock chunks, assert system message contains expected text.
- **`tests/test_generator.py`** — mock `anthropic.messages.create`, assert response shape matches `ChatResponse`.
- **`tests/test_api.py`** — FastAPI `TestClient`, POST `/chat` with mocked generator, assert 200 + schema.

No integration tests against the live Anthropic API (avoids cost and network dependency in CI).

---

## 11. Implementation Order

1. `src/core/config.py`
2. `src/ingestion/embeddings.py` → `vectorstore.py` → `pipeline.py`
3. Run `uv run python -m src.ingestion.pipeline` to build the vector store
4. `src/rag/retriever.py` → `prompt.py` → `generator.py`
5. `src/api/schemas.py` → `routes.py` → `main.py`
6. Update `pyproject.toml`
7. Write tests
