# Ingestion, RAG & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three empty scaffold modules (`src/ingestion/`, `src/rag/`, `src/api/`) to produce a working RAG endpoint that answers questions grounded in Kardec's five Spiritist works.

**Architecture:** Parsed JSON chunks are embedded with a local sentence-transformers model and stored in ChromaDB. On each request the query is optionally condensed (multi-turn history), embedded, and used to retrieve top-K chunks filtered by cosine distance. If no chunks pass the threshold, a fixed Portuguese "not found" message is returned without calling Claude; otherwise Claude Haiku generates a grounded answer. The API is stateless — the client manages conversation history.

**Tech Stack:** `sentence-transformers` (`paraphrase-multilingual-mpnet-base-v2`), `chromadb`, `anthropic` SDK (`claude-haiku-4-5`), `fastapi`, `uvicorn`, `pydantic-settings`

## Global Constraints

- Python 3.12+
- Package manager: `uv` — install with `uv sync --group dev`, run with `uv run`
- Embedding model: `paraphrase-multilingual-mpnet-base-v2` (768-dim vectors, ~420 MB download on first use, then cached)
- LLM: `claude-haiku-4-5` for both generation and query condensation
- Vector distance metric: cosine (`hnsw:space = cosine`, range 0–2), hard threshold `MAX_DISTANCE = 1.2`
- `.env` must contain `ANTHROPIC_API_KEY`
- All user-facing responses in Portuguese (Brazil)
- Do not modify anything under `src/parsing/` or `data/markdown_files/`
- Spec: `docs/superpowers/specs/2026-06-20-ingestion-rag-api-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Replace openai/tiktoken with new deps |
| `src/core/__init__.py` | Create | Package marker |
| `src/core/config.py` | Create | Pydantic-settings `Settings` singleton |
| `.env.example` | Create | Template for required env vars |
| `tests/__init__.py` | Create | Package marker |
| `tests/conftest.py` | Create | Session-scoped env var fixture |
| `tests/fixtures/__init__.py` | Create | Package marker |
| `tests/fixtures/sample_chunks.json` | Create | 2-chunk fixture for ingestion tests |
| `src/ingestion/__init__.py` | Create if missing | Package marker |
| `src/ingestion/embeddings.py` | Fill | `encode()` via SentenceTransformer singleton |
| `src/ingestion/vectorstore.py` | Fill | `VectorStore` wrapping ChromaDB |
| `src/ingestion/pipeline.py` | Fill | `run_ingestion()` — JSON → embed → upsert |
| `src/rag/__init__.py` | Create if missing | Package marker |
| `src/rag/retriever.py` | Fill | `retrieve()` with distance filter |
| `src/rag/prompt.py` | Fill | `build_messages()` — system prompt + message list |
| `src/rag/generator.py` | Fill | `condense_query()` + `generate()` |
| `src/api/__init__.py` | Create if missing | Package marker |
| `src/api/schemas.py` | Fill | Pydantic request/response models |
| `src/api/routes.py` | Fill | FastAPI router: `POST /chat`, `GET /health` |
| `src/api/main.py` | Fill | FastAPI app instantiation |

---

### Task 1: Config & Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `src/core/__init__.py`
- Create: `src/core/config.py`
- Create: `.env.example`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `from src.core.config import settings` — a `Settings` instance with all fields below

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest


def test_settings_has_correct_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from src.core.config import Settings
    s = Settings()
    assert s.top_k == 5
    assert s.max_distance == 1.2
    assert s.max_history_turns == 10
    assert s.chroma_collection == "kardec_docs"
    assert s.chat_model == "claude-haiku-4-5"
    assert s.condenser_model == "claude-haiku-4-5"


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pydantic import ValidationError
    from src.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError` (src.core.config does not exist yet)

- [ ] **Step 3: Update `pyproject.toml`**

Replace the entire `[project]` block:

```toml
[project]
name = "kardec-study-assistant"
version = "0.1.0"
description = "Backend and LLM study assistant based on Allan Kardec's works"
authors = [
    { name = "Mary Camila" }
]
requires-python = ">=3.12"

dependencies = [
    "anthropic>=0.20.0",
    "sentence-transformers>=2.7.0",
    "chromadb>=0.4.0",
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv",
]

[dependency-groups]
dev = [
    "black",
    "isort",
    "pytest",
    "httpx",
]

[tool.uv]
package = false

[tool.black]
line-length = 88
target-version = ["py312"]

[tool.isort]
profile = "black"
```

Then install:

```bash
uv sync --group dev
```

- [ ] **Step 4: Create `src/core/__init__.py`** (empty file)

- [ ] **Step 5: Create `src/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    chat_model: str = "claude-haiku-4-5"
    condenser_model: str = "claude-haiku-4-5"
    top_k: int = 5
    max_distance: float = 1.2
    max_history_turns: int = 10
    chroma_path: str = "data/embeddings/"
    chroma_collection: str = "kardec_docs"
    json_dir: str = "data/json_files"


settings = Settings()
```

- [ ] **Step 6: Create `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

- [ ] **Step 7: Create `tests/__init__.py`** (empty file)

- [ ] **Step 8: Create `tests/conftest.py`**

```python
import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def set_test_env():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 2 tests PASS

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml src/core/__init__.py src/core/config.py .env.example tests/__init__.py tests/conftest.py tests/test_config.py
git commit -m "feat: add config and update dependencies"
```

---

### Task 2: Embedding Model

**Files:**
- Fill: `src/ingestion/embeddings.py`
- Create: `src/ingestion/__init__.py` (if missing)
- Create: `tests/test_embeddings.py`

**Interfaces:**
- Consumes: `settings.embedding_model` from Task 1
- Produces: `encode(texts: list[str]) -> list[list[float]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embeddings.py
from src.ingestion.embeddings import encode


def test_encode_returns_one_vector_per_input():
    results = encode(["reencarnação", "alma espírita"])
    assert len(results) == 2


def test_encode_vector_dimension_is_768():
    results = encode(["qualquer texto"])
    assert len(results[0]) == 768  # paraphrase-multilingual-mpnet-base-v2


def test_encode_same_text_is_deterministic():
    a = encode(["Deus"])
    b = encode(["Deus"])
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_embeddings.py -v
```

Expected: `ImportError` — `embeddings.py` is empty

- [ ] **Step 3: Create `src/ingestion/__init__.py`** (empty file, skip if already exists)

- [ ] **Step 4: Fill `src/ingestion/embeddings.py`**

```python
from sentence_transformers import SentenceTransformer

from src.core.config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    return _get_model().encode(texts, convert_to_numpy=True).tolist()
```

- [ ] **Step 5: Run tests to verify they pass**

> Note: the first run downloads the model (~420 MB). Subsequent runs use the local cache.

```bash
uv run pytest tests/test_embeddings.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/__init__.py src/ingestion/embeddings.py tests/test_embeddings.py
git commit -m "feat: add embedding model wrapper"
```

---

### Task 3: Vector Store

**Files:**
- Fill: `src/ingestion/vectorstore.py`
- Create: `tests/test_vectorstore.py`

**Interfaces:**
- Consumes: nothing (standalone ChromaDB wrapper)
- Produces:
  - `VectorStore(path: str, collection_name: str)`
  - `.upsert(ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None`
  - `.query(embedding: list[float], n_results: int) -> list[dict]`
    - each dict: `{"content": str, "metadata": dict, "distance": float}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vectorstore.py
import pytest
from src.ingestion.vectorstore import VectorStore

_META = {
    "book": "O Livro dos Espíritos",
    "part": "",
    "chapter": "",
    "chapter_title": "Da Encarnação",
    "item_number": "132",
    "subchunk_index": 1,
    "total_subchunks": 1,
}


@pytest.fixture
def store(tmp_path):
    return VectorStore(str(tmp_path), "test_col")


def test_upsert_and_query_returns_document(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["alma e reencarnação"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert len(results) == 1
    assert results[0]["content"] == "alma e reencarnação"


def test_query_returns_low_distance_for_same_vector(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["alma e reencarnação"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert results[0]["distance"] < 0.01  # identical vectors → cosine distance ~0


def test_query_returns_metadata(store):
    store.upsert(
        ids=["doc1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["texto"],
        metadatas=[_META],
    )
    results = store.query([1.0, 0.0, 0.0], n_results=1)
    assert results[0]["metadata"]["book"] == "O Livro dos Espíritos"
    assert results[0]["metadata"]["item_number"] == "132"


def test_upsert_is_idempotent(store):
    for _ in range(2):
        store.upsert(
            ids=["doc1"],
            embeddings=[[1.0, 0.0, 0.0]],
            documents=["texto"],
            metadatas=[_META],
        )
    results = store.query([1.0, 0.0, 0.0], n_results=5)
    assert len(results) == 1  # not duplicated
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_vectorstore.py -v
```

Expected: `ImportError` — `vectorstore.py` is empty

- [ ] **Step 3: Fill `src/ingestion/vectorstore.py`**

```python
import chromadb


class VectorStore:
    def __init__(self, path: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], n_results: int) -> list[dict]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"content": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_vectorstore.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/vectorstore.py tests/test_vectorstore.py
git commit -m "feat: add ChromaDB vector store wrapper"
```

---

### Task 4: Ingestion Pipeline

**Files:**
- Fill: `src/ingestion/pipeline.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/sample_chunks.json`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `encode()` from Task 2, `VectorStore` from Task 3, `settings.json_dir / chroma_path / chroma_collection` from Task 1
- Produces: `run_ingestion() -> None` (populates ChromaDB as a side effect)

- [ ] **Step 1: Create `tests/fixtures/__init__.py`** (empty file)

- [ ] **Step 2: Create `tests/fixtures/sample_chunks.json`**

```json
[
  {
    "book": "O Livro dos Espíritos",
    "part": "SEGUNDA PARTE",
    "chapter": "CAPÍTULO I",
    "chapter_title": "Da Encarnação dos Espíritos",
    "item_number": "132",
    "subchunk_index": 1,
    "total_subchunks": 1,
    "content": "A encarnação dos Espíritos tem por fim fazê-los progredir.",
    "footnotes": [{"number": "1", "content": "Nota de rodapé de exemplo."}]
  },
  {
    "book": "O Livro dos Espíritos",
    "part": "SEGUNDA PARTE",
    "chapter": "CAPÍTULO I",
    "chapter_title": "Da Encarnação dos Espíritos",
    "item_number": "133",
    "subchunk_index": 1,
    "total_subchunks": 1,
    "content": "O Espírito encarnado habita o corpo do homem.",
    "footnotes": []
  }
]
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_pipeline.py
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
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: `ImportError` — `pipeline.py` is empty

- [ ] **Step 5: Fill `src/ingestion/pipeline.py`**

```python
import json
import os

from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

BATCH_SIZE = 64


def _build_document(chunk: dict) -> str:
    doc = chunk["content"]
    for note in chunk.get("footnotes", []):
        doc += f"\n[Nota {note['number']}] {note['content']}"
    return doc


def _build_id(stem: str, chunk: dict) -> str:
    return f"{stem}_{chunk['item_number']}_{chunk['subchunk_index']}"


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
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 2 tests PASS

- [ ] **Step 7: Run real ingestion on all five books**

> Requires the parsing pipeline to have run first: `uv run python -m src.parsing.parsing_pipeline`

```bash
uv run python -m src.ingestion.pipeline
```

Expected: one line per book ending with "Ingestion complete."

- [ ] **Step 8: Commit**

```bash
git add src/ingestion/pipeline.py tests/fixtures/__init__.py tests/fixtures/sample_chunks.json tests/test_pipeline.py
git commit -m "feat: add ingestion pipeline"
```

---

### Task 5: Retriever

**Files:**
- Fill: `src/rag/retriever.py`
- Create: `src/rag/__init__.py` (if missing)
- Create: `tests/test_retriever.py`

**Interfaces:**
- Consumes: `encode()` from Task 2, `VectorStore.query()` from Task 3, `settings.top_k / max_distance / chroma_path / chroma_collection` from Task 1
- Produces: `retrieve(query: str, top_k: int | None = None) -> list[dict]`
  - Returns only chunks where `distance <= settings.max_distance`
  - Each dict: `{"content": str, "metadata": dict, "distance": float}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_retriever.py
from unittest.mock import MagicMock

import pytest

from src.rag.retriever import retrieve

_MOCK_RESULTS = [
    {"content": "alma espírita", "metadata": {"book": "X", "chapter_title": "A", "item_number": "1"}, "distance": 0.5},
    {"content": "texto irrelevante", "metadata": {"book": "Y", "chapter_title": "B", "item_number": "2"}, "distance": 1.5},
]


@pytest.fixture(autouse=True)
def mock_deps(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = _MOCK_RESULTS
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    monkeypatch.setattr("src.rag.retriever.encode", lambda texts: [[0.1] * 768])


def test_retrieve_filters_chunks_above_max_distance():
    results = retrieve("alma")
    assert len(results) == 1
    assert results[0]["content"] == "alma espírita"


def test_retrieve_keeps_chunks_at_or_below_max_distance():
    results = retrieve("alma")
    assert all(r["distance"] <= 1.2 for r in results)


def test_retrieve_returns_empty_when_all_too_distant(monkeypatch):
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"content": "irrelevante", "metadata": {}, "distance": 1.9},
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve("budismo")
    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_retriever.py -v
```

Expected: `ImportError` — `retriever.py` is empty

- [ ] **Step 3: Create `src/rag/__init__.py`** (empty file, skip if already exists)

- [ ] **Step 4: Fill `src/rag/retriever.py`**

```python
from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return _store


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k
    embedding = encode([query])[0]
    results = _get_store().query(embedding, n_results=top_k)
    return [r for r in results if r["distance"] <= settings.max_distance]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_retriever.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/rag/__init__.py src/rag/retriever.py tests/test_retriever.py
git commit -m "feat: add RAG retriever with distance filtering"
```

---

### Task 6: Prompt Builder

**Files:**
- Fill: `src/rag/prompt.py`
- Create: `tests/test_prompt.py`

**Interfaces:**
- Consumes: nothing from prior tasks (pure function)
- Produces: `build_messages(question: str, chunks: list[dict], history: list[dict], max_history_turns: int = 10) -> tuple[str, list[dict]]`
  - First element: system prompt string containing formatted retrieved passages
  - Second element: messages list `[{"role": "user"|"assistant", "content": str}, ...]` ending with the current question

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompt.py
from src.rag.prompt import build_messages

_CHUNK = {
    "content": "A encarnação tem por fim fazê-los progredir.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação dos Espíritos",
        "item_number": "132",
    },
    "distance": 0.4,
}


def test_system_contains_passage_content():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "A encarnação tem por fim" in system


def test_system_contains_book_name():
    system, _ = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert "O Livro dos Espíritos" in system


def test_messages_ends_with_user_question():
    _, messages = build_messages("O que é reencarnação?", [_CHUNK], [])
    assert messages[-1] == {"role": "user", "content": "O que é reencarnação?"}


def test_history_is_prepended_to_messages():
    history = [
        {"role": "user", "content": "Pergunta anterior"},
        {"role": "assistant", "content": "Resposta anterior"},
    ]
    _, messages = build_messages("Nova pergunta", [_CHUNK], history)
    assert messages[0] == {"role": "user", "content": "Pergunta anterior"}
    assert messages[-1]["content"] == "Nova pergunta"


def test_history_is_capped_at_max_history_turns():
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(20)
    ]
    _, messages = build_messages("fim", [_CHUNK], history, max_history_turns=4)
    assert len(messages) == 5  # 4 history turns + 1 current question
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_prompt.py -v
```

Expected: `ImportError` — `prompt.py` is empty

- [ ] **Step 3: Fill `src/rag/prompt.py`**

```python
_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos da doutrina espírita, fundamentado exclusivamente \
nas cinco obras de Allan Kardec. Responda SOMENTE com base nas passagens recuperadas abaixo. \
Se as passagens não contiverem informação suficiente para responder, diga isso explicitamente \
— não invente doutrina.

Responda em Português (Brasil). Separe claramente o que vem do texto original e o que é \
sua explicação.

[PASSAGENS RECUPERADAS]
{passages}"""


def _format_passage(index: int, chunk: dict) -> str:
    m = chunk["metadata"]
    header = f"[{index}] Obra: {m['book']}"
    if m.get("chapter_title"):
        header += f" | Capítulo: {m['chapter_title']}"
    if m.get("item_number"):
        header += f" | Item: {m['item_number']}"
    return f"{header}\n    \"{chunk['content']}\""


def build_messages(
    question: str,
    chunks: list[dict],
    history: list[dict],
    max_history_turns: int = 10,
) -> tuple[str, list[dict]]:
    passages = "\n\n".join(_format_passage(i + 1, c) for i, c in enumerate(chunks))
    system = _SYSTEM_TEMPLATE.format(passages=passages)

    messages = [
        {"role": t["role"], "content": t["content"]}
        for t in history[-max_history_turns:]
    ]
    messages.append({"role": "user", "content": question})

    return system, messages
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_prompt.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/prompt.py tests/test_prompt.py
git commit -m "feat: add prompt builder"
```

---

### Task 7: Generator

**Files:**
- Fill: `src/rag/generator.py`
- Create: `tests/test_generator.py`

**Interfaces:**
- Consumes:
  - `retrieve(query: str) -> list[dict]` from Task 5
  - `build_messages(question, chunks, history, max_history_turns) -> tuple[str, list[dict]]` from Task 6
  - `settings.condenser_model / chat_model / max_history_turns / anthropic_api_key` from Task 1
- Produces: `generate(question: str, history: list[dict]) -> dict`
  - Returns `{"answer": str, "sources": list[dict], "not_found": bool}`
  - Source dict shape: `{"book": str, "chapter": str | None, "item_number": str | None}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generator.py
from unittest.mock import MagicMock, patch

import pytest

from src.rag.generator import generate

_CHUNKS = [
    {
        "content": "A encarnação tem por fim fazê-los progredir.",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
        "distance": 0.4,
    }
]


@pytest.fixture
def mock_retrieve(monkeypatch):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: _CHUNKS)


@pytest.fixture
def mock_client(monkeypatch):
    response = MagicMock()
    response.content = [MagicMock(text="Resposta gerada.")]
    client = MagicMock()
    client.messages.create.return_value = response
    monkeypatch.setattr("src.rag.generator._get_client", lambda: client)
    return client


def test_generate_returns_answer(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert result["answer"] == "Resposta gerada."
    assert result["not_found"] is False


def test_generate_returns_deduplicated_sources(mock_retrieve, mock_client):
    result = generate("O que é reencarnação?", [])
    assert len(result["sources"]) == 1
    assert result["sources"][0]["book"] == "O Livro dos Espíritos"
    assert result["sources"][0]["item_number"] == "132"


def test_generate_not_found_when_no_chunks(monkeypatch, mock_client):
    monkeypatch.setattr("src.rag.generator.retrieve", lambda q, **kw: [])
    result = generate("Fale sobre budismo", [])
    assert result["not_found"] is True
    assert result["sources"] == []
    mock_client.messages.create.assert_not_called()


def test_generate_calls_condenser_when_history_present(mock_retrieve, mock_client):
    history = [
        {"role": "user", "content": "O que é reencarnação?"},
        {"role": "assistant", "content": "É o retorno do espírito."},
    ]
    with patch("src.rag.generator.condense_query", return_value="consulta condensada") as mock_cond:
        generate("E o que mais ele diz?", history)
    mock_cond.assert_called_once()


def test_generate_skips_condenser_without_history(mock_retrieve, mock_client):
    with patch("src.rag.generator.condense_query") as mock_cond:
        generate("O que é reencarnação?", [])
    mock_cond.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_generator.py -v
```

Expected: `ImportError` — `generator.py` is empty

- [ ] **Step 3: Fill `src/rag/generator.py`**

```python
import anthropic

from src.core.config import settings
from src.rag.prompt import build_messages
from src.rag.retriever import retrieve

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec informações suficientes para responder "
    "a essa pergunta. Por favor, reformule sua dúvida ou consulte diretamente as obras."
)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def condense_query(question: str, history: list[dict]) -> str:
    history_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in history[-settings.max_history_turns :]
    )
    prompt = (
        f"Dado este histórico de conversa:\n{history_text}\n\n"
        f"Reescreva a seguinte pergunta como uma consulta de busca independente e completa. "
        f"Retorne apenas a consulta reescrita, sem explicações.\n\nPergunta: {question}"
    )
    response = _get_client().messages.create(
        model=settings.condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate(question: str, history: list[dict]) -> dict:
    search_query = condense_query(question, history) if history else question
    chunks = retrieve(search_query)

    if not chunks:
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "not_found": True}

    system, messages = build_messages(question, chunks, history, settings.max_history_turns)
    response = _get_client().messages.create(
        model=settings.chat_model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    seen: set[tuple] = set()
    sources = []
    for chunk in chunks:
        m = chunk["metadata"]
        key = (m["book"], m.get("chapter_title", ""), m.get("item_number", ""))
        if key not in seen:
            seen.add(key)
            sources.append({
                "book": m["book"],
                "chapter": m.get("chapter_title") or None,
                "item_number": m.get("item_number") or None,
            })

    return {
        "answer": response.content[0].text,
        "sources": sources,
        "not_found": False,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_generator.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/generator.py tests/test_generator.py
git commit -m "feat: add RAG generator with query condensation and not-found handling"
```

---

### Task 8: API Layer

**Files:**
- Fill: `src/api/schemas.py`
- Fill: `src/api/routes.py`
- Fill: `src/api/main.py`
- Create: `src/api/__init__.py` (if missing)
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: `generate(question: str, history: list[dict]) -> dict` from Task 7
- Produces:
  - `POST /chat` body: `{"question": str, "history": [{"role": str, "content": str}]}` → `{"answer": str, "sources": [...], "not_found": bool}`
  - `GET /health` → `{"status": "ok"}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_ANSWER_RESULT = {
    "answer": "A reencarnação permite a evolução do espírito.",
    "sources": [{"book": "O Livro dos Espíritos", "chapter": "Da Encarnação", "item_number": "132"}],
    "not_found": False,
}

_NOT_FOUND_RESULT = {
    "answer": "Não encontrei nas obras de Kardec informações suficientes…",
    "sources": [],
    "not_found": True,
}


def test_chat_returns_200():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        response = client.post("/chat", json={"question": "O que é reencarnação?", "history": []})
    assert response.status_code == 200


def test_chat_response_has_expected_fields():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        data = client.post("/chat", json={"question": "O que é reencarnação?", "history": []}).json()
    assert "answer" in data
    assert "sources" in data
    assert "not_found" in data
    assert data["not_found"] is False


def test_chat_not_found_flag_is_true_when_out_of_doctrine():
    with patch("src.api.routes.generate", return_value=_NOT_FOUND_RESULT):
        data = client.post("/chat", json={"question": "Fale sobre budismo", "history": []}).json()
    assert data["not_found"] is True
    assert data["sources"] == []


def test_chat_passes_history_to_generator():
    history = [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Olá!"}]
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT) as mock_gen:
        client.post("/chat", json={"question": "Continua?", "history": history})
    _, called_history = mock_gen.call_args[0]
    assert len(called_history) == 2


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_api.py -v
```

Expected: `ImportError` — API files are empty

- [ ] **Step 3: Create `src/api/__init__.py`** (empty file, skip if already exists)

- [ ] **Step 4: Fill `src/api/schemas.py`**

```python
from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Source(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str | None = None


class ChatRequest(BaseModel):
    question: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    not_found: bool = False
```

- [ ] **Step 5: Fill `src/api/routes.py`**

```python
from fastapi import APIRouter

from src.api.schemas import ChatRequest, ChatResponse, Source
from src.rag.generator import generate

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in request.history]
    result = generate(request.question, history)
    return ChatResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        not_found=result["not_found"],
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Fill `src/api/main.py`**

```python
from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(title="Dialogando com a Doutrina")
app.include_router(router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_api.py -v
```

Expected: 5 tests PASS

- [ ] **Step 8: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 9: Smoke test the running server**

In one terminal:

```bash
uv run uvicorn src.api.main:app --reload
```

In a second terminal:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "O que Kardec diz sobre reencarnação?", "history": []}' \
  | python3 -m json.tool
```

Expected: JSON with `answer` (doctrine text), `sources` (list with book/chapter/item), and `"not_found": false`

Try an off-doctrine question to verify the hard gate:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é o budismo?", "history": []}' \
  | python3 -m json.tool
```

Expected: `"not_found": true` and the fixed Portuguese message in `answer`

- [ ] **Step 10: Commit**

```bash
git add src/api/__init__.py src/api/schemas.py src/api/routes.py src/api/main.py tests/test_api.py
git commit -m "feat: add FastAPI chat endpoint"
```
