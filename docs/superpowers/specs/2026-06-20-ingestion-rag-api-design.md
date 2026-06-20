# Design: Ingestion, RAG, and API Layers

**Date:** 2026-06-20
**Scope:** Implement `src/ingestion/`, `src/rag/`, and `src/api/` — the three empty scaffolds remaining after the parsing layer is complete.

---

## 1. Context

The parsing pipeline (`src/parsing/`) is fully implemented and produces structured JSON chunks from Kardec's five books. Each chunk has these fields:

```json
{
  "book": "O Livro dos Espíritos",
  "part": "SEGUNDA PARTE — O MUNDO ESPÍRITA",
  "chapter": "CAPÍTULO I",
  "chapter_title": "Da Encarnação dos Espíritos",
  "item_number": "132",
  "subchunk_index": 1,
  "total_subchunks": 1,
  "content": "...",
  "footnotes": [{ "number": "1", "content": "..." }]
}
```

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

Metadata stored per chunk: `book`, `part`, `chapter`, `chapter_title`, `item_number`, `subchunk_index`, `total_subchunks`. Footnotes are omitted from metadata (too large) but included in the `content` field if non-empty.

Document ID format: `{book_slug}_{item_number}_{subchunk_index}` — stable across re-runs, allowing upsert to be idempotent.

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
  query VectorStore
  return top_k results with content + metadata
```

Returns raw retrieved chunks — no filtering or re-ranking at this stage.

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

```
Client
  POST /chat {question, history}
        ↓
  routes.py → generator.generate()
        ↓
  [if history] condenser → claude-haiku-4-5 → condensed_query
        ↓
  retriever.retrieve(condensed_query)
        ↓
  EmbeddingModel.encode(condensed_query)
        ↓
  VectorStore.query() → top 5 chunks
        ↓
  prompt.build_messages(original_question, chunks, history)
        ↓
  claude-haiku-4-5 → answer text
        ↓
  ChatResponse {answer, sources}
        ↓
  Client
```

---

## 8. Error Handling

- **No chunks retrieved** (distance too large): generator passes empty chunks list; system prompt instructs Claude to say it couldn't find relevant content. No special error path.
- **Anthropic API error**: let FastAPI's default 500 propagate for the PoC. No retry logic.
- **Missing JSON files** (ingestion not run): ingestion pipeline prints a warning and skips; ChromaDB collection will be empty, which triggers the "no chunks" path above.

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
