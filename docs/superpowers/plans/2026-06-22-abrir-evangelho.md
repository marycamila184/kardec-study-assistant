# Abrir o Evangelho Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /evangelho` — a no-LLM endpoint that returns the deterministic daily passage from *O Evangelho segundo o Espiritismo*, changing at midnight, stable across restarts.

**Architecture:** A thin selector module (`src/rag/evangelho.py`) fetches all Evangelho chunks from ChromaDB via the existing `get_by_filter`, sorts them deterministically by metadata, seeds Python's `random` with today's ISO date string, and picks one chunk. The route wraps this in a 200/503 response.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB (via existing `VectorStore`), Python stdlib `random` + `datetime`.

## Global Constraints

- No LLM call in this feature — pure retrieval, no AI generation.
- 503 (not 500) when no Evangelho chunks indexed; body: `{"error": "evangelho_not_indexed"}`.
- Deterministic selection: `random.seed(datetime.date.today().isoformat())` then `random.choice(sorted_chunks)`.
- Sort chunks by `(item_number, subchunk_index)` metadata fields before seeding — stable ordering independent of ChromaDB insertion order.
- `content` is verbatim from the ChromaDB document (no modification).
- No `import pytest` in test files.
- Run `uv run isort src/` after modifying any file in `src/`.
- Run tests with `uv run pytest`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/rag/evangelho.py` | Create | Daily passage selector: filter → sort → seed → choose |
| `src/api/schemas.py` | Modify | Add `EvangelhoSource`, `EvangelhoResponse` Pydantic models |
| `src/api/routes.py` | Modify | Add `GET /evangelho` endpoint |
| `tests/test_evangelho.py` | Create | Unit tests for `get_daily_passage()` |
| `tests/test_api.py` | Modify | Integration tests for `GET /evangelho` endpoint |

---

### Task 1: Evangelho daily passage selector

**Files:**
- Create: `src/rag/evangelho.py`
- Create: `tests/test_evangelho.py`

**Interfaces:**
- Consumes: `VectorStore.get_by_filter(where: dict) -> list[dict]` (already implemented in `src/ingestion/vectorstore.py`); `_get_store() -> VectorStore` from `src/rag/retriever.py`.
- Produces: `get_daily_passage() -> dict | None` — returns `None` when no Evangelho chunks are indexed; otherwise returns:
  ```python
  {
      "date": str,            # ISO date string, e.g. "2026-06-22"
      "content": str,         # verbatim chunk document
      "source": {
          "book": str,
          "chapter_title": str | None,
          "item_number": str | None,
          "subchunk_index": int | None,
          "total_subchunks": int | None,
      },
  }
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evangelho.py`:

```python
from unittest.mock import MagicMock, patch

from src.rag.evangelho import get_daily_passage

_CHUNK_1 = {
    "content": "Bem-aventurados os puros de coração.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Bem-aventuranças",
        "item_number": "section-4",
        "subchunk_index": 1,
        "total_subchunks": 1,
    },
    "distance": 0.0,
}

_CHUNK_2 = {
    "content": "Amai-vos uns aos outros.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Amor ao próximo",
        "item_number": "section-7",
        "subchunk_index": 1,
        "total_subchunks": 2,
    },
    "distance": 0.0,
}


def _mock_store(chunks):
    store = MagicMock()
    store.get_by_filter.return_value = chunks
    return store


def test_returns_none_when_no_chunks():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([])):
        result = get_daily_passage()
    assert result is None


def test_returns_passage_with_correct_shape():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result is not None
    assert "date" in result
    assert "content" in result
    assert "source" in result


def test_content_comes_from_selected_chunk():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["content"] == "Bem-aventurados os puros de coração."


def test_source_fields_populated_from_chunk_metadata():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["source"]["book"] == "O Evangelho segundo o Espiritismo"
    assert result["source"]["chapter_title"] == "Bem-aventuranças"
    assert result["source"]["item_number"] == "section-4"
    assert result["source"]["subchunk_index"] == 1
    assert result["source"]["total_subchunks"] == 1


def test_same_date_returns_same_passage():
    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1, _CHUNK_2])):
        result1 = get_daily_passage()
        result2 = get_daily_passage()
    assert result1["content"] == result2["content"]


def test_date_field_is_today_isoformat():
    import datetime

    with patch("src.rag.evangelho._get_store", return_value=_mock_store([_CHUNK_1])):
        result = get_daily_passage()
    assert result["date"] == datetime.date.today().isoformat()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_evangelho.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.evangelho'` (or similar import error).

- [ ] **Step 3: Implement `src/rag/evangelho.py`**

Create `src/rag/evangelho.py`:

```python
import datetime
import random

from src.rag.retriever import _get_store

EVANGELHO_BOOK = "O Evangelho segundo o Espiritismo"


def get_daily_passage() -> dict | None:
    chunks = _get_store().get_by_filter({"book": {"$eq": EVANGELHO_BOOK}})
    if not chunks:
        return None
    chunks.sort(
        key=lambda c: (
            c["metadata"].get("item_number", ""),
            c["metadata"].get("subchunk_index", 0),
        )
    )
    today = datetime.date.today().isoformat()
    random.seed(today)
    chunk = random.choice(chunks)
    meta = chunk["metadata"]
    return {
        "date": today,
        "content": chunk["content"],
        "source": {
            "book": EVANGELHO_BOOK,
            "chapter_title": meta.get("chapter_title"),
            "item_number": meta.get("item_number"),
            "subchunk_index": meta.get("subchunk_index"),
            "total_subchunks": meta.get("total_subchunks"),
        },
    }
```

- [ ] **Step 4: Run isort**

```bash
uv run isort src/
```

Expected: no output (or `Fixing src/rag/evangelho.py` if it reorganizes anything).

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_evangelho.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/rag/evangelho.py tests/test_evangelho.py
git commit -m "feat: add Evangelho daily passage selector"
```

---

### Task 2: API schema, endpoint, and integration tests

**Files:**
- Modify: `src/api/schemas.py` (add `EvangelhoSource`, `EvangelhoResponse`)
- Modify: `src/api/routes.py` (add `GET /evangelho`, import `get_daily_passage`, import new schemas)
- Modify: `tests/test_api.py` (add 3 evangelho tests)

**Interfaces:**
- Consumes: `get_daily_passage() -> dict | None` from Task 1.
- Produces: `GET /evangelho` → 200 `EvangelhoResponse` | 503 `{"error": "evangelho_not_indexed"}`.

- [ ] **Step 1: Write the failing integration tests**

Append to the bottom of `tests/test_api.py`:

```python
_EVANGELHO_PASSAGE = {
    "date": "2026-06-22",
    "content": "Bem-aventurados os que têm puro o coração.",
    "source": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Bem-aventuranças",
        "item_number": "section-4",
        "subchunk_index": 1,
        "total_subchunks": 1,
    },
}


def test_evangelho_returns_200():
    with patch("src.api.routes.get_daily_passage", return_value=_EVANGELHO_PASSAGE):
        response = client.get("/evangelho")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-06-22"
    assert data["content"] == "Bem-aventurados os que têm puro o coração."


def test_evangelho_response_has_source_fields():
    with patch("src.api.routes.get_daily_passage", return_value=_EVANGELHO_PASSAGE):
        data = client.get("/evangelho").json()
    assert data["source"]["book"] == "O Evangelho segundo o Espiritismo"
    assert data["source"]["chapter_title"] == "Bem-aventuranças"
    assert data["source"]["item_number"] == "section-4"
    assert data["source"]["subchunk_index"] == 1
    assert data["source"]["total_subchunks"] == 1


def test_evangelho_returns_503_when_not_indexed():
    with patch("src.api.routes.get_daily_passage", return_value=None):
        response = client.get("/evangelho")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "evangelho_not_indexed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_api.py::test_evangelho_returns_200 tests/test_api.py::test_evangelho_response_has_source_fields tests/test_api.py::test_evangelho_returns_503_when_not_indexed -v
```

Expected: `AttributeError` or `404` — the route does not exist yet.

- [ ] **Step 3: Add `EvangelhoSource` and `EvangelhoResponse` to `src/api/schemas.py`**

Append to the bottom of `src/api/schemas.py` (after `ReflectResponse`):

```python
class EvangelhoSource(BaseModel):
    book: str
    chapter_title: str | None = None
    item_number: str | None = None
    subchunk_index: int | None = None
    total_subchunks: int | None = None


class EvangelhoResponse(BaseModel):
    date: str
    content: str
    source: EvangelhoSource
```

- [ ] **Step 4: Add `GET /evangelho` to `src/api/routes.py`**

The full updated `src/api/routes.py` (replace entirely — isort requires alphabetical ordering within each import group):

```python
from fastapi import APIRouter, HTTPException

from src.api.paths import load_all_paths, load_path
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    EvangelhoResponse,
    EvangelhoSource,
    PathDetail,
    PathSummary,
    ReflectRequest,
    ReflectResponse,
    Source,
    StudyRequest,
    StudyResponse,
)
from src.core.config import settings
from src.rag.evangelho import get_daily_passage
from src.rag.generator import generate
from src.rag.mode_detector import detect_suggested_mode
from src.rag.reflect import reflect as reflect_fn
from src.rag.study import study as study_item_fn

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in request.history]
    result = generate(request.question, history)
    suggested_mode = detect_suggested_mode(request.question)
    return ChatResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        not_found=result["not_found"],
        suggested_mode=suggested_mode,
    )


@router.get("/paths", response_model=list[PathSummary])
def list_paths() -> list[PathSummary]:
    paths = load_all_paths(settings.paths_dir)
    return [PathSummary(**p) for p in paths]


@router.get("/paths/{path_id}", response_model=PathDetail)
def get_path(path_id: str) -> PathDetail:
    path = load_path(settings.paths_dir, path_id)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "path_not_found", "path_id": path_id},
        )
    return PathDetail(**path)


@router.post("/study", response_model=StudyResponse)
def study(request: StudyRequest) -> StudyResponse:
    result = study_item_fn(request.book, request.item_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "item_not_found", "item_number": request.item_number},
        )
    return StudyResponse(**result)


@router.post("/reflect", response_model=ReflectResponse)
def reflect_situation(request: ReflectRequest) -> ReflectResponse:
    result = reflect_fn(request.situation)
    return ReflectResponse(**result)


@router.get("/evangelho", response_model=EvangelhoResponse)
def evangelho() -> EvangelhoResponse:
    passage = get_daily_passage()
    if passage is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "evangelho_not_indexed"},
        )
    return EvangelhoResponse(
        date=passage["date"],
        content=passage["content"],
        source=EvangelhoSource(**passage["source"]),
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Run isort**

```bash
uv run isort src/
```

Expected: no output (imports in `routes.py` are already alphabetically ordered within each group).

- [ ] **Step 6: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASSED, including the 3 new evangelho API tests.

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas.py src/api/routes.py tests/test_api.py
git commit -m "feat: add GET /evangelho endpoint for daily Evangelho passage"
```
