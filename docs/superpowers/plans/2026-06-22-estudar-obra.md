# Estudar uma Obra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Funcionalidade #1 — three new API endpoints (`GET /paths`, `GET /paths/{path_id}`, `POST /study`) and `suggested_mode` detection on `POST /chat`, so users can study specific items from Kardec's works via curated learning paths.

**Architecture:** ChromaDB metadata filter retrieves exact item chunks; semantic search retrieves related items; a single LLM call with an educator prompt returns structured JSON. Paths are curated JSON files in `data/paths/`; client owns progress tracking. Mode detection is regex-only on the `/chat` request.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB, sentence-transformers (`paraphrase-multilingual-mpnet-base-v2`), OpenAI-compatible client (Groq), Pydantic v2, uv.

## Global Constraints

- All commands run via `uv run` (e.g., `uv run pytest`)
- Test runner: `uv run pytest`
- Formatter: `uv run black src/ tests/` and `uv run isort src/ tests/`
- No LLM calls in tests — always mock `_get_client()` and `encode()`
- All text in Portuguese (Brasil); LLM prompts in Portuguese
- Never cut a real LLM call in tests; use `unittest.mock.MagicMock` or `monkeypatch`
- The `GROQ_API_KEY` env var must be set before any import of `src.core.config` — `tests/conftest.py` already handles this via `os.environ.setdefault`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `src/ingestion/vectorstore.py` | Add `get_by_filter(where)` for metadata-only lookup |
| Modify | `src/rag/retriever.py` | Add `retrieve_by_item(book, item_number)` |
| Create | `src/rag/study_prompt.py` | Build educator system prompt; parse LLM JSON response |
| Create | `src/rag/study.py` | Orchestrate direct lookup → related → LLM → structured result |
| Create | `src/rag/mode_detector.py` | Regex detection of study-mode query intent |
| Create | `src/api/paths.py` | Load path JSON files from `data/paths/` |
| Modify | `src/core/config.py` | Add `paths_dir` setting |
| Create | `data/paths/fundamentos-da-doutrina.json` | First curated learning path |
| Modify | `src/api/schemas.py` | Add `PathSummary`, `PathDetail`, `PathStep`, `StudyRequest`, `StudyResponse`, `RelatedItem`, `StudySource`; add `suggested_mode` to `ChatResponse` |
| Modify | `src/api/routes.py` | Add `GET /paths`, `GET /paths/{path_id}`, `POST /study`; add `suggested_mode` to `/chat` |
| Modify | `tests/test_vectorstore.py` | Add 2 tests for `get_by_filter` |
| Modify | `tests/test_retriever.py` | Add 2 tests for `retrieve_by_item` |
| Create | `tests/test_study_prompt.py` | Tests for prompt builder and JSON parser |
| Create | `tests/test_study.py` | Tests for `study()` function |
| Create | `tests/test_mode_detector.py` | Tests for `detect_suggested_mode()` |
| Create | `tests/test_paths.py` | Tests for `load_all_paths()` and `load_path()` |
| Modify | `tests/test_config.py` | Add `paths_dir` default assertion |
| Modify | `tests/test_api.py` | Add tests for 3 new endpoints and `suggested_mode` on `/chat` |

---

### Task 1: VectorStore.get_by_filter + retrieve_by_item

**Files:**
- Modify: `src/ingestion/vectorstore.py` (after line 39)
- Modify: `src/rag/retriever.py` (after line 20)
- Test: `tests/test_vectorstore.py`
- Test: `tests/test_retriever.py`

**Interfaces:**
- Produces: `VectorStore.get_by_filter(where: dict) -> list[dict]` — each dict has `content`, `metadata`, `distance: 0.0`
- Produces: `retrieve_by_item(book: str, item_number: str) -> list[dict]` — same shape as `retrieve()`

- [ ] **Step 1: Write failing tests for `get_by_filter`**

Add to the bottom of `tests/test_vectorstore.py`:

```python
def test_get_by_filter_returns_matching_chunk(store):
    store.upsert(
        ids=["doc1", "doc2"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        documents=["encarnação", "outro texto"],
        metadatas=[
            {**_META, "item_number": "132"},
            {**_META, "item_number": "133"},
        ],
    )
    results = store.get_by_filter({"item_number": {"$eq": "132"}})
    assert len(results) == 1
    assert results[0]["content"] == "encarnação"
    assert results[0]["distance"] == 0.0


def test_get_by_filter_returns_empty_when_no_match(store):
    results = store.get_by_filter({"item_number": {"$eq": "999"}})
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_vectorstore.py::test_get_by_filter_returns_matching_chunk tests/test_vectorstore.py::test_get_by_filter_returns_empty_when_no_match -v
```

Expected: `AttributeError: 'VectorStore' object has no attribute 'get_by_filter'`

- [ ] **Step 3: Implement `get_by_filter` in `src/ingestion/vectorstore.py`**

Add after the `query` method (line 39):

```python
    def get_by_filter(self, where: dict) -> list[dict]:
        result = self._collection.get(
            where=where,
            include=["documents", "metadatas"],
        )
        return [
            {"content": doc, "metadata": meta, "distance": 0.0}
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]
```

- [ ] **Step 4: Run vectorstore tests to verify they pass**

```
uv run pytest tests/test_vectorstore.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Write failing tests for `retrieve_by_item`**

Add to the bottom of `tests/test_retriever.py`:

```python
from src.rag.retriever import retrieve_by_item

def test_retrieve_by_item_calls_get_by_filter_with_correct_where(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [_MOCK_RESULTS[0]]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "1")
    assert len(results) == 1
    mock_store.get_by_filter.assert_called_once_with(
        {"$and": [{"book": {"$eq": "O Livro dos Espíritos"}}, {"item_number": {"$eq": "1"}}]}
    )


def test_retrieve_by_item_returns_empty_list_when_not_found(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = []
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    results = retrieve_by_item("O Livro dos Espíritos", "999")
    assert results == []
```

- [ ] **Step 6: Run retriever tests to verify new tests fail**

```
uv run pytest tests/test_retriever.py::test_retrieve_by_item_calls_get_by_filter_with_correct_where tests/test_retriever.py::test_retrieve_by_item_returns_empty_list_when_not_found -v
```

Expected: `ImportError` or `AttributeError` — `retrieve_by_item` does not exist yet

- [ ] **Step 7: Implement `retrieve_by_item` in `src/rag/retriever.py`**

Add after `retrieve()` (line 20):

```python
def retrieve_by_item(book: str, item_number: str) -> list[dict]:
    where = {"$and": [{"book": {"$eq": book}}, {"item_number": {"$eq": item_number}}]}
    return _get_store().get_by_filter(where)
```

- [ ] **Step 8: Run all retriever tests to verify they pass**

```
uv run pytest tests/test_retriever.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/ingestion/vectorstore.py src/rag/retriever.py tests/test_vectorstore.py tests/test_retriever.py
git commit -m "feat: add get_by_filter to VectorStore and retrieve_by_item to retriever"
```

---

### Task 2: Study prompt module

**Files:**
- Create: `src/rag/study_prompt.py`
- Create: `tests/test_study_prompt.py`

**Interfaces:**
- Consumes: `main_text: str`, `related_chunks: list[dict]` (each dict has `content`, `metadata.book`, `metadata.item_number`)
- Produces: `build_study_messages(main_text, related_chunks) -> tuple[str, list[dict]]` — `(system_prompt, messages_list)`
- Produces: `parse_llm_json(text: str) -> tuple[str, str]` — `(explanation, practical_example)`

- [ ] **Step 1: Create `tests/test_study_prompt.py` with failing tests**

```python
import pytest
from src.rag.study_prompt import build_study_messages, parse_llm_json


_RELATED = [
    {
        "content": "O espírito evolui.",
        "metadata": {"book": "O Livro dos Espíritos", "item_number": "100"},
        "distance": 0.3,
    }
]


def test_main_passage_appears_in_system():
    system, _ = build_study_messages("alma e corpo", [])
    assert "alma e corpo" in system


def test_related_passage_appears_in_system():
    system, _ = build_study_messages("texto", _RELATED)
    assert "O espírito evolui." in system


def test_json_instruction_in_system():
    system, _ = build_study_messages("texto", [])
    assert "JSON" in system


def test_messages_contains_user_prompt():
    _, messages = build_study_messages("texto", [])
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert isinstance(messages[0]["content"], str)


def test_parse_llm_json_extracts_fields():
    text = '{"explanation": "A alma existe.", "practical_example": "Como quando sonhamos."}'
    expl, ex = parse_llm_json(text)
    assert expl == "A alma existe."
    assert ex == "Como quando sonhamos."


def test_parse_llm_json_strips_markdown_fences():
    text = '```json\n{"explanation": "A.", "practical_example": "B."}\n```'
    expl, ex = parse_llm_json(text)
    assert expl == "A."
    assert ex == "B."


def test_parse_llm_json_falls_back_on_invalid_json():
    text = "não é JSON válido"
    expl, ex = parse_llm_json(text)
    assert expl == "não é JSON válido"
    assert ex == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_study_prompt.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.study_prompt'`

- [ ] **Step 3: Create `src/rag/study_prompt.py`**

```python
import json
import re

_SYSTEM_TEMPLATE = """\
Você é um educador especializado na obra de Allan Kardec. Baseando-se SOMENTE nos \
trechos abaixo, retorne APENAS um JSON válido com as chaves exatas:
{{
  "explanation": "<explicação em linguagem moderna incluindo conexões com as referências>",
  "practical_example": "<exemplo prático da vida cotidiana>"
}}

Nunca elabore doutrina além dos trechos. Se o trecho for muito breve, diga isso \
explicitamente dentro do JSON. Se o tema não estiver nos livros, diga que não encontrou.

[TRECHO PRINCIPAL]
{main_passage}

[REFERÊNCIAS RELACIONADAS]
{related_passages}"""


def _format_related(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma)"
    parts = []
    for c in chunks:
        m = c["metadata"]
        parts.append(f"[{m['book']} | Item {m['item_number']}]\n\"{c['content']}\"")
    return "\n\n".join(parts)


def build_study_messages(main_text: str, related_chunks: list[dict]) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        main_passage=main_text,
        related_passages=_format_related(related_chunks),
    )
    messages = [{"role": "user", "content": "Explique o trecho acima."}]
    return system, messages


def parse_llm_json(text: str) -> tuple[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()
    try:
        data = json.loads(text)
        return data.get("explanation", ""), data.get("practical_example", "")
    except (json.JSONDecodeError, AttributeError):
        return text, ""
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_study_prompt.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/study_prompt.py tests/test_study_prompt.py
git commit -m "feat: add study prompt builder and LLM JSON parser"
```

---

### Task 3: Study generator

**Files:**
- Create: `src/rag/study.py`
- Create: `tests/test_study.py`

**Interfaces:**
- Consumes: `retrieve_by_item(book, item_number)` from Task 1; `retrieve(query, top_k)` from existing retriever; `build_study_messages`, `parse_llm_json` from Task 2
- Produces: `study(book: str, item_number: str) -> dict | None`
  - Returns `None` when item not found
  - Returns dict with keys: `original_text: str`, `explanation: str`, `practical_example: str`, `related_items: list[dict]`, `sources: list[dict]`, `generation_failed: bool`

- [ ] **Step 1: Create `tests/test_study.py` with failing tests**

```python
from unittest.mock import MagicMock, patch

import pytest

from src.rag.study import study

_CHUNK = {
    "content": "A alma é imortal.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "150",
        "chapter_title": "Da Alma",
    },
    "distance": 0.0,
}

_LLM_JSON = '{"explanation": "Explicação.", "practical_example": "Exemplo."}'


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_study_returns_none_when_item_not_found():
    with patch("src.rag.study.retrieve_by_item", return_value=[]):
        result = study("O Livro dos Espíritos", "999")
    assert result is None


def test_study_returns_original_text():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["original_text"] == "A alma é imortal."


def test_study_returns_explanation_from_llm():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["explanation"] == "Explicação."
    assert result["practical_example"] == "Exemplo."


def test_study_sets_generation_failed_on_llm_error():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API error")
        result = study("O Livro dos Espíritos", "150")
    assert result["generation_failed"] is True
    assert result["original_text"] == "A alma é imortal."
    assert result["explanation"] == ""


def test_study_excludes_same_item_from_related():
    same_item_chunk = {**_CHUNK, "distance": 0.1}
    other_chunk = {
        "content": "outro texto",
        "metadata": {"book": "O Livro dos Espíritos", "item_number": "200", "chapter_title": ""},
        "distance": 0.4,
    }
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[same_item_chunk, other_chunk]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert all(r["item_number"] != "150" for r in result["related_items"])


def test_study_sources_include_chunk_metadata():
    with (
        patch("src.rag.study.retrieve_by_item", return_value=[_CHUNK]),
        patch("src.rag.study.retrieve", return_value=[]),
        patch("src.rag.study._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = study("O Livro dos Espíritos", "150")
    assert result["sources"][0]["item_number"] == "150"
    assert result["sources"][0]["book"] == "O Livro dos Espíritos"
    assert result["sources"][0]["chapter_title"] == "Da Alma"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_study.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.study'`

- [ ] **Step 3: Create `src/rag/study.py`**

```python
from openai import OpenAI

from src.core.config import settings
from src.rag.retriever import retrieve, retrieve_by_item
from src.rag.study_prompt import build_study_messages, parse_llm_json

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def study(book: str, item_number: str) -> dict | None:
    chunks = retrieve_by_item(book, item_number)
    if not chunks:
        return None

    original_text = "\n\n".join(c["content"] for c in chunks)

    all_related = retrieve(original_text, top_k=6)
    related = [
        r for r in all_related
        if not (
            r["metadata"]["item_number"] == item_number
            and r["metadata"]["book"] == book
        )
    ][:3]

    system, messages = build_study_messages(original_text, related)

    explanation = ""
    practical_example = ""
    generation_failed = False
    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        explanation, practical_example = parse_llm_json(response.choices[0].message.content)
    except Exception:
        generation_failed = True

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in chunks
    ]

    related_items = [
        {
            "book": r["metadata"]["book"],
            "item_number": r["metadata"]["item_number"],
            "preview": r["content"][:200],
        }
        for r in related
    ]

    return {
        "original_text": original_text,
        "explanation": explanation,
        "practical_example": practical_example,
        "related_items": related_items,
        "sources": sources,
        "generation_failed": generation_failed,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_study.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/study.py tests/test_study.py
git commit -m "feat: add study generator with direct lookup, related items, and LLM explanation"
```

---

### Task 4: Mode detector

**Files:**
- Create: `src/rag/mode_detector.py`
- Create: `tests/test_mode_detector.py`

**Interfaces:**
- Produces: `detect_suggested_mode(question: str) -> str | None` — returns `"estudar_obra"` or `None`

- [ ] **Step 1: Create `tests/test_mode_detector.py` with failing tests**

```python
from src.rag.mode_detector import detect_suggested_mode


def test_detects_questao_with_number():
    assert detect_suggested_mode("o que é questão 132?") == "estudar_obra"


def test_detects_item_with_number():
    assert detect_suggested_mode("explique o item 45") == "estudar_obra"


def test_detects_q_dot_with_number():
    assert detect_suggested_mode("qual o significado de Q. 76?") == "estudar_obra"


def test_detects_explique_a_questao():
    assert detect_suggested_mode("explique a questão sobre espíritos") == "estudar_obra"


def test_detects_o_que_diz_with_number():
    assert detect_suggested_mode("o que diz Kardec no item 200") == "estudar_obra"


def test_returns_none_for_generic_question():
    assert detect_suggested_mode("o que é reencarnação?") is None


def test_returns_none_for_empty_string():
    assert detect_suggested_mode("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_mode_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.mode_detector'`

- [ ] **Step 3: Create `src/rag/mode_detector.py`**

```python
import re

_STUDY_PATTERNS = [
    re.compile(r"\bquestão\s+\d+", re.IGNORECASE),
    re.compile(r"\bitem\s+\d+", re.IGNORECASE),
    re.compile(r"\bq\.\s*\d+", re.IGNORECASE),
    re.compile(r"explique\s+a\s+questão", re.IGNORECASE),
    re.compile(r"o\s+que\s+(diz|fala)\s+.+\d+", re.IGNORECASE),
]


def detect_suggested_mode(question: str) -> str | None:
    if any(p.search(question) for p in _STUDY_PATTERNS):
        return "estudar_obra"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_mode_detector.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/mode_detector.py tests/test_mode_detector.py
git commit -m "feat: add mode detector for study-intent queries"
```

---

### Task 5: Path loader + Settings + example path

**Files:**
- Create: `src/api/paths.py`
- Modify: `src/core/config.py`
- Create: `data/paths/fundamentos-da-doutrina.json`
- Modify: `tests/test_config.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Produces: `load_all_paths(paths_dir: str) -> list[dict]` — list of summary dicts (no `steps` key)
- Produces: `load_path(paths_dir: str, path_id: str) -> dict | None` — full path dict with `steps`, or `None`
- `Settings.paths_dir: str` defaults to `"data/paths"`

- [ ] **Step 1: Create `tests/test_paths.py` with failing tests**

```python
import json
import pytest
from src.api.paths import load_all_paths, load_path

_PATH_DATA = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "steps": [
        {"book": "O Livro dos Espíritos", "item_number": "1", "label": "O que é Deus?"},
        {"book": "O Livro dos Espíritos", "item_number": "2", "label": "Atributos da divindade"},
    ],
}


@pytest.fixture
def paths_dir(tmp_path):
    (tmp_path / "fundamentos.json").write_text(
        json.dumps(_PATH_DATA, ensure_ascii=False), encoding="utf-8"
    )
    return str(tmp_path)


def test_load_all_paths_returns_summaries(paths_dir):
    paths = load_all_paths(paths_dir)
    assert len(paths) == 1
    assert paths[0]["id"] == "fundamentos"
    assert paths[0]["step_count"] == 2
    assert "steps" not in paths[0]


def test_load_all_paths_returns_empty_when_dir_missing():
    paths = load_all_paths("/nonexistent/path/xyz")
    assert paths == []


def test_load_all_paths_ignores_non_json_files(paths_dir, tmp_path):
    (tmp_path / "notes.txt").write_text("ignore me")
    paths = load_all_paths(paths_dir)
    assert len(paths) == 1


def test_load_path_returns_full_detail_with_steps(paths_dir):
    path = load_path(paths_dir, "fundamentos")
    assert path["id"] == "fundamentos"
    assert len(path["steps"]) == 2
    assert path["steps"][0]["item_number"] == "1"


def test_load_path_returns_none_when_not_found(paths_dir):
    result = load_path(paths_dir, "nonexistent")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_paths.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.api.paths'`

- [ ] **Step 3: Create `src/api/paths.py`**

```python
import json
import os


def load_all_paths(paths_dir: str) -> list[dict]:
    if not os.path.isdir(paths_dir):
        return []
    summaries = []
    for filename in sorted(os.listdir(paths_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(paths_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        summaries.append({
            "id": data["id"],
            "title": data["title"],
            "description": data["description"],
            "level": data["level"],
            "step_count": len(data["steps"]),
        })
    return summaries


def load_path(paths_dir: str, path_id: str) -> dict | None:
    filepath = os.path.join(paths_dir, f"{path_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_paths.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Add `paths_dir` to Settings**

In `src/core/config.py`, add after line 16 (`json_dir` setting):

```python
    paths_dir: str = "data/paths"
```

- [ ] **Step 6: Add `paths_dir` assertion to `tests/test_config.py`**

In `test_settings_has_correct_defaults`, add inside the assert block:

```python
    assert s.paths_dir == "data/paths"
```

- [ ] **Step 7: Run config tests to verify they pass**

```
uv run pytest tests/test_config.py -v
```

Expected: both tests PASS

- [ ] **Step 8: Create `data/paths/` directory and example path**

```bash
mkdir -p data/paths
```

Create `data/paths/fundamentos-da-doutrina.json`:

```json
{
  "id": "fundamentos-da-doutrina",
  "title": "Fundamentos da Doutrina Espírita",
  "description": "Para quem está começando. Apresenta os pilares do espiritismo em ordem natural.",
  "level": "iniciante",
  "steps": [
    {"book": "O Livro dos Espíritos", "item_number": "1", "label": "O que é Deus?"},
    {"book": "O Livro dos Espíritos", "item_number": "2", "label": "Atributos da divindade"},
    {"book": "O Livro dos Espíritos", "item_number": "76", "label": "Existem espíritos maus?"},
    {"book": "O Livro dos Espíritos", "item_number": "132", "label": "O que é a encarnação?"},
    {"book": "O Livro dos Espíritos", "item_number": "166", "label": "Por que encarnamos?"},
    {"book": "O Livro dos Espíritos", "item_number": "219", "label": "O que acontece após a morte?"}
  ]
}
```

- [ ] **Step 9: Commit**

```bash
git add src/api/paths.py src/core/config.py data/paths/fundamentos-da-doutrina.json tests/test_paths.py tests/test_config.py
git commit -m "feat: add path loader, paths_dir setting, and first curated learning path"
```

---

### Task 6: Schemas + Routes + API tests

**Files:**
- Modify: `src/api/schemas.py`
- Modify: `src/api/routes.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `study()` from Task 3; `detect_suggested_mode()` from Task 4; `load_all_paths()`, `load_path()` from Task 5
- New Pydantic models: `PathStep`, `PathSummary`, `PathDetail`, `RelatedItem`, `StudySource`, `StudyRequest`, `StudyResponse`
- Updated: `ChatResponse` gains `suggested_mode: str | None = None`

- [ ] **Step 1: Write failing API tests**

Add to the bottom of `tests/test_api.py`:

```python
_STUDY_RESULT = {
    "original_text": "A alma é imortal.",
    "explanation": "A alma continua existindo após a morte do corpo físico.",
    "practical_example": "Como quando acordamos de um sonho muito vívido.",
    "related_items": [],
    "sources": [
        {"book": "O Livro dos Espíritos", "chapter_title": "Da Alma", "item_number": "150"}
    ],
    "generation_failed": False,
}

_PATH_SUMMARY = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "step_count": 2,
}

_PATH_DETAIL = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "steps": [
        {"book": "O Livro dos Espíritos", "item_number": "1", "label": "O que é Deus?"}
    ],
}


def test_study_returns_200():
    with patch("src.api.routes.study_item_fn", return_value=_STUDY_RESULT):
        response = client.post(
            "/study", json={"book": "O Livro dos Espíritos", "item_number": "150"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["original_text"] == "A alma é imortal."
    assert data["generation_failed"] is False


def test_study_returns_404_when_item_not_found():
    with patch("src.api.routes.study_item_fn", return_value=None):
        response = client.post(
            "/study", json={"book": "O Livro dos Espíritos", "item_number": "999"}
        )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "item_not_found"


def test_list_paths_returns_200_with_summaries():
    with patch("src.api.routes.load_all_paths", return_value=[_PATH_SUMMARY]):
        response = client.get("/paths")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "fundamentos"
    assert "steps" not in data[0]


def test_get_path_returns_full_detail():
    with patch("src.api.routes.load_path", return_value=_PATH_DETAIL):
        response = client.get("/paths/fundamentos")
    assert response.status_code == 200
    data = response.json()
    assert len(data["steps"]) == 1


def test_get_path_returns_404_when_not_found():
    with patch("src.api.routes.load_path", return_value=None):
        response = client.get("/paths/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "path_not_found"


def test_chat_includes_suggested_mode_when_detected():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch("src.api.routes.detect_suggested_mode", return_value="estudar_obra"),
    ):
        data = client.post(
            "/chat", json={"question": "explique a questão 132", "history": []}
        ).json()
    assert data["suggested_mode"] == "estudar_obra"


def test_chat_suggested_mode_is_none_for_generic_question():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch("src.api.routes.detect_suggested_mode", return_value=None),
    ):
        data = client.post(
            "/chat", json={"question": "o que é amor?", "history": []}
        ).json()
    assert data["suggested_mode"] is None
```

- [ ] **Step 2: Run new tests to verify they fail**

```
uv run pytest tests/test_api.py::test_study_returns_200 tests/test_api.py::test_list_paths_returns_200_with_summaries tests/test_api.py::test_chat_includes_suggested_mode_when_detected -v
```

Expected: failures because new routes and schemas don't exist yet

- [ ] **Step 3: Update `src/api/schemas.py`**

Replace the entire file content with:

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
    suggested_mode: str | None = None


class PathStep(BaseModel):
    book: str
    item_number: str
    label: str


class PathSummary(BaseModel):
    id: str
    title: str
    description: str
    level: str
    step_count: int


class PathDetail(BaseModel):
    id: str
    title: str
    description: str
    level: str
    steps: list[PathStep]


class RelatedItem(BaseModel):
    book: str
    item_number: str
    preview: str


class StudySource(BaseModel):
    book: str
    chapter_title: str | None = None
    item_number: str


class StudyRequest(BaseModel):
    book: str
    item_number: str
    conversation_history: list[Message] = []


class StudyResponse(BaseModel):
    original_text: str
    explanation: str
    practical_example: str
    related_items: list[RelatedItem]
    sources: list[StudySource]
    generation_failed: bool = False
```

- [ ] **Step 4: Update `src/api/routes.py`**

Replace the entire file content with:

```python
from fastapi import APIRouter, HTTPException

from src.api.paths import load_all_paths, load_path
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    PathDetail,
    PathSummary,
    Source,
    StudyRequest,
    StudyResponse,
)
from src.core.config import settings
from src.rag.generator import generate
from src.rag.mode_detector import detect_suggested_mode
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


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Run all API tests to verify they pass**

```
uv run pytest tests/test_api.py -v
```

Expected: all tests PASS (5 original + 7 new = 12 total)

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas.py src/api/routes.py tests/test_api.py
git commit -m "feat: add /study, /paths endpoints and suggested_mode on /chat"
```
