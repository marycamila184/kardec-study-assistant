# Batch A — Backend Quality Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve RAG retrieval quality and observability, and route situational `/chat` questions toward Refletir, without touching the large frontend conversation architecture (Batch B).

**Architecture:** Four independent changes. A1 extracts the existing `/chat` query condenser into a shared module and wires it into `/reflect`'s multi-turn retrieval. A2 narrows the Explicador related-items query to the first subchunk. A3 adds failure-path logging across the four RAG pipeline modules. A4 extends `detect_suggested_mode` to also return `"refletir"` for situational questions and adds one additive frontend button.

**Tech Stack:** Python 3.12, FastAPI, pytest, `unittest.mock`; React (Vite) frontend with no test harness (manual verification for UI).

## Global Constraints

- Package manager: **uv**. Run tests with `uv run pytest`. Format with `uv run black src/ tests/` and `uv run isort src/ tests/`.
- All existing tests must continue to pass after every task.
- Portuguese (pt-BR) for all user-facing copy.
- Existing test convention: patch module-local imported names (e.g. `src.rag.reflect.condense_query`), mock the LLM client via `patch("src.rag.<mod>.get_client")` returning a `MagicMock` whose `.chat.completions.create` returns `MagicMock(choices=[MagicMock(message=MagicMock(content=...))])`.
- Refletir accent color (frontend button): `#C8856A`. Estudar button reference: `App.jsx:806-820`.
- End every commit message with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task 1: Extract `condense_query` into a shared module (A1a)

**Files:**
- Create: `src/rag/query_condenser.py`
- Modify: `src/rag/generator.py:1-35` (remove local `condense_query`, import it)
- Create: `tests/test_query_condenser.py`

**Interfaces:**
- Produces: `condense_query(question: str, history: list[dict]) -> str` in `src/rag/query_condenser.py`. Uses `settings.condenser_model`, `settings.max_history_turns`, and `get_client()`. Returns the stripped re"standalone search query" string.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

Create `tests/test_query_condenser.py`:

```python
from unittest.mock import MagicMock, patch

from src.rag.query_condenser import condense_query


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_condense_query_returns_stripped_content():
    history = [{"role": "user", "content": "O que é reencarnação?"}]
    with patch("src.rag.query_condenser.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response("  consulta reescrita  ")
        )
        result = condense_query("e o que mais?", history)
    assert result == "consulta reescrita"


def test_condense_query_sends_history_and_question_to_llm():
    history = [{"role": "user", "content": "pergunta anterior"}]
    with patch("src.rag.query_condenser.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response("x")
        )
        condense_query("nova pergunta", history)
        prompt = mock_client.return_value.chat.completions.create.call_args.kwargs[
            "messages"
        ][0]["content"]
    assert "pergunta anterior" in prompt
    assert "nova pergunta" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_query_condenser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.rag.query_condenser'`

- [ ] **Step 3: Create the module**

Create `src/rag/query_condenser.py` (moved verbatim from `generator.py`):

```python
from src.core.config import settings
from src.rag.llm_client import get_client


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
    response = get_client().chat.completions.create(
        model=settings.condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
```

- [ ] **Step 4: Update `generator.py` to import instead of defining**

In `src/rag/generator.py`, delete the local `condense_query` function (currently lines 20-35) and add the import near the top imports:

```python
from src.rag.query_condenser import condense_query
```

Remove the now-unused `from src.rag.llm_client import get_client` only if `get_client` is no longer referenced elsewhere in `generator.py` — it **is** still used for the main chat completion, so keep it.

- [ ] **Step 5: Run tests to verify pass (new + existing generator tests unaffected)**

Run: `uv run pytest tests/test_query_condenser.py tests/test_generator.py -v`
Expected: PASS. In particular `test_generate_calls_condenser_when_history_present` and `test_generate_falls_back_to_raw_question_when_condenser_fails` still pass because they patch `src.rag.generator.condense_query`, which remains a name in the generator namespace via the new import.

- [ ] **Step 6: Format and commit**

```bash
uv run isort src/ tests/ && uv run black src/ tests/
git add src/rag/query_condenser.py src/rag/generator.py tests/test_query_condenser.py
git commit -m "refactor: extract condense_query into shared query_condenser module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Condense query for `/reflect` multi-turn retrieval (A1b)

**Files:**
- Modify: `src/rag/reflect.py:1-26` (import condenser; condense before retrieve when history present)
- Modify: `tests/test_reflect.py` (add tests)

**Interfaces:**
- Consumes: `condense_query(question, history)` from Task 1.
- Produces: no signature change to `reflect(...)`. Behavior: retrieval query is condensed when `conversation_history` is non-empty; raw `situation` otherwise; raw `situation` on condense failure.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reflect.py`:

```python
def test_reflect_condenses_query_when_history_present():
    history = [
        {"role": "user", "content": "situação original"},
        {"role": "assistant", "content": "reflexão anterior"},
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch(
            "src.rag.reflect.condense_query", return_value="consulta condensada"
        ) as mock_cond,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("e se ela não me perdoar?", conversation_history=history)
    mock_cond.assert_called_once()
    assert mock_retrieve.call_args[0][0] == "consulta condensada"


def test_reflect_skips_condense_without_history():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch("src.rag.reflect.condense_query") as mock_cond,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        reflect("minha situação")
    mock_cond.assert_not_called()
    assert mock_retrieve.call_args[0][0] == "minha situação"


def test_reflect_falls_back_to_raw_situation_when_condense_fails():
    history = [{"role": "user", "content": "anterior"}]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]) as mock_retrieve,
        patch("src.rag.reflect.get_client") as mock_client,
        patch(
            "src.rag.reflect.condense_query", side_effect=RuntimeError("down")
        ),
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(_LLM_JSON)
        )
        result = reflect("situação atual", conversation_history=history)
    assert mock_retrieve.call_args[0][0] == "situação atual"
    assert result["generation_failed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reflect.py -k "condense or raw_situation" -v`
Expected: FAIL — `test_reflect_condenses_query_when_history_present` fails because `condense_query` is not imported in `src.rag.reflect` (AttributeError on patch), and the retrieve query is still the raw situation.

- [ ] **Step 3: Wire the condenser into `reflect.py`**

In `src/rag/reflect.py`, add the import alongside the existing imports:

```python
from src.rag.query_condenser import condense_query
```

Then change the retrieval block. Replace:

```python
    history = conversation_history or []
    try:
        chunks = retrieve(situation, top_k=5)
    except Exception:
```

with:

```python
    history = conversation_history or []
    search_query = situation
    if history:
        try:
            search_query = condense_query(situation, history)
        except Exception:
            search_query = situation
    try:
        chunks = retrieve(search_query, top_k=5)
    except Exception:
```

(The `except Exception` block that follows is unchanged in this task; logging is added in Task 5.)

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_reflect.py -v`
Expected: PASS (new tests plus all existing reflect tests — existing ones patch `retrieve` ignoring its argument, so they are unaffected).

- [ ] **Step 5: Format and commit**

```bash
uv run isort src/ tests/ && uv run black src/ tests/
git add src/rag/reflect.py tests/test_reflect.py
git commit -m "feat: condense query for /reflect multi-turn retrieval

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Tighten Explicador related-items query to first subchunk (A2)

**Files:**
- Modify: `src/rag/explicador.py:24-25`
- Modify: `tests/test_explicador.py` (add a multi-subchunk test)

**Interfaces:**
- Produces: no signature change to `explicar(...)`. Behavior: the related-items `retrieve` call is issued with `chunks[0]["content"]` (first subchunk) instead of the full concatenated `original_text`. `curar(...)` and `build_explicador_messages(...)` still receive the full `original_text`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_explicador.py`:

```python
_MULTI_CHUNK_A = {
    "content": "Primeiro subtrecho, curto e específico.",
    "footnote_context": "",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação",
        "item_number": "132",
    },
    "distance": 0.0,
}
_MULTI_CHUNK_B = {
    "content": "Segundo subtrecho, com outro assunto diluidor.",
    "footnote_context": "",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "chapter_title": "Da Encarnação",
        "item_number": "132",
    },
    "distance": 0.0,
}


def test_explicar_retrieves_related_using_first_subchunk_only():
    llm_json = (
        '{"contexto": "c", "conceitos_chave": [], "perguntas": []}'
    )
    with (
        patch(
            "src.rag.explicador.retrieve_by_item",
            return_value=[_MULTI_CHUNK_A, _MULTI_CHUNK_B],
        ),
        patch("src.rag.explicador.retrieve", return_value=[]) as mock_retrieve,
        patch("src.rag.explicador.curar", return_value=[]) as mock_curar,
        patch("src.rag.explicador.get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = (
            _make_llm_response(llm_json)
        )
        explicar("O Livro dos Espíritos", "132")
    # related retrieval uses ONLY the first subchunk
    assert mock_retrieve.call_args[0][0] == "Primeiro subtrecho, curto e específico."
    # curar still receives the FULL concatenated original text
    full_text = (
        "Primeiro subtrecho, curto e específico.\n\n"
        "Segundo subtrecho, com outro assunto diluidor."
    )
    assert mock_curar.call_args[0][0] == full_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_explicador.py::test_explicar_retrieves_related_using_first_subchunk_only -v`
Expected: FAIL — `retrieve` is currently called with the full concatenated `original_text`, so `call_args[0][0]` is the full text, not the first subchunk.

- [ ] **Step 3: Change the query in `explicador.py`**

In `src/rag/explicador.py`, replace:

```python
    try:
        all_related = retrieve(original_text, top_k=6)
    except Exception:
        all_related = []
```

with:

```python
    related_query = chunks[0]["content"]
    try:
        all_related = retrieve(related_query, top_k=6)
    except Exception:
        all_related = []
```

(`chunks` is guaranteed non-empty here — the function returns `None` earlier if `not chunks`.)

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_explicador.py -v`
Expected: PASS. Existing `test_explicar_degrades_gracefully_when_related_retrieval_fails` still passes: its single chunk's content equals `original_text`, and `curar` is still asserted with `"1. Que é Deus?"`.

- [ ] **Step 5: Format and commit**

```bash
uv run isort src/ tests/ && uv run black src/ tests/
git add src/rag/explicador.py tests/test_explicador.py
git commit -m "feat: retrieve Explicador related items using first subchunk only

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Bidirectional mode detection — suggest Refletir (A4 backend)

**Files:**
- Modify: `src/rag/mode_detector.py`
- Modify: `tests/test_mode_detector.py`

**Interfaces:**
- Produces: `detect_suggested_mode(question: str) -> str | None` now returns `"estudar_obra"` (study patterns, highest priority), `"refletir"` (situational patterns), or `None`. `estudar_obra` wins when both match.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_mode_detector.py`:

```python
def test_detects_refletir_for_fear():
    assert detect_suggested_mode("tenho medo de morrer") == "refletir"


def test_detects_refletir_for_grief():
    assert detect_suggested_mode("perdi minha mãe e não sei lidar") == "refletir"


def test_detects_refletir_for_anxiety():
    assert detect_suggested_mode("estou com muita ansiedade ultimamente") == "refletir"


def test_estudar_wins_over_refletir_when_both_match():
    # situational word "medo" + explicit item lookup -> study intent wins
    assert detect_suggested_mode("tenho medo, explique a questão 132") == "estudar_obra"


def test_generic_question_still_returns_none():
    assert detect_suggested_mode("o que é reencarnação?") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mode_detector.py -k "refletir or wins" -v`
Expected: FAIL — situational questions currently return `None`.

- [ ] **Step 3: Extend `mode_detector.py`**

Replace the contents of `src/rag/mode_detector.py` with:

```python
import re

_STUDY_PATTERNS = [
    re.compile(r"\bquestão\s+\d+", re.IGNORECASE),
    re.compile(r"\bitem\s+\d+", re.IGNORECASE),
    re.compile(r"\bq\.\s*\d+", re.IGNORECASE),
    re.compile(r"explique\s+a\s+questão", re.IGNORECASE),
    re.compile(r"o\s+que\s+(diz|fala)\s+.+\d+", re.IGNORECASE),
]

# Situational / emotional cues that suggest the Refletir flow rather than a
# dry factual answer. Kept intentionally soft — a false positive only surfaces
# an optional button, never changes the answer itself.
_SITUATIONAL_PATTERNS = [
    re.compile(r"\b(medo|receio|pavor)\b", re.IGNORECASE),
    re.compile(r"\b(luto|perdi|faleceu|morreu)\b", re.IGNORECASE),
    re.compile(r"\bansiedade\b|\bansios[oa]\b|\bang[uú]stia\b", re.IGNORECASE),
    re.compile(r"\b(sozinh[oa]|solid[ãa]o)\b", re.IGNORECASE),
    re.compile(r"\b(sofrimento|sofrendo|tristeza|triste|deprimid[oa])\b", re.IGNORECASE),
    re.compile(r"\b(culpa|culpad[oa])\b", re.IGNORECASE),
    re.compile(r"\b(raiva|[óo]dio|rancor|m[áa]goa)\b", re.IGNORECASE),
    re.compile(r"\bdesespero\b|\bdesesperad[oa]\b", re.IGNORECASE),
    re.compile(r"n[ãa]o\s+sei\s+(o\s+que\s+fazer|como\s+lidar|lidar)", re.IGNORECASE),
    re.compile(r"\bpassando\s+por\b", re.IGNORECASE),
]


def detect_suggested_mode(question: str) -> str | None:
    if any(p.search(question) for p in _STUDY_PATTERNS):
        return "estudar_obra"
    if any(p.search(question) for p in _SITUATIONAL_PATTERNS):
        return "refletir"
    return None
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_mode_detector.py -v`
Expected: PASS (new tests + all 7 existing tests).

- [ ] **Step 5: Format and commit**

```bash
uv run isort src/ tests/ && uv run black src/ tests/
git add src/rag/mode_detector.py tests/test_mode_detector.py
git commit -m "feat: detect situational questions and suggest Refletir mode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Failure-path logging across RAG pipelines (A3)

**Files:**
- Modify: `src/rag/generator.py`, `src/rag/reflect.py`, `src/rag/explicador.py`, `src/rag/curador.py`
- Modify: `tests/test_generator.py`, `tests/test_reflect.py`, `tests/test_explicador.py`, `tests/test_curador.py`

**Interfaces:**
- Consumes: final state of `generator.py`/`reflect.py`/`explicador.py` after Tasks 1-4.
- Produces: each module has `logger = logging.getLogger(__name__)` and emits a log record on each failure/fallback path. No behavior change.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_generator.py`:

```python
import logging


def test_generate_logs_on_retrieval_error(monkeypatch, mock_client, caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    monkeypatch.setattr("src.rag.generator.retrieve", _raise)
    with caplog.at_level(logging.ERROR, logger="src.rag.generator"):
        generate("pergunta", [])
    assert any("retriev" in r.message.lower() for r in caplog.records)
```

Add to `tests/test_reflect.py`:

```python
import logging


def test_reflect_logs_on_retrieval_error(caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("db error")

    with (
        patch("src.rag.reflect.retrieve", side_effect=_raise),
        caplog.at_level(logging.ERROR, logger="src.rag.reflect"),
    ):
        reflect("situação")
    assert any("retriev" in r.message.lower() for r in caplog.records)
```

Add to `tests/test_explicador.py`:

```python
import logging


def test_explicar_logs_on_llm_error(caplog):
    def _raise(*args, **kwargs):
        raise RuntimeError("API error")

    with (
        patch(
            "src.rag.explicador.retrieve_by_item", return_value=[_CHUNK_WITH_FOOTNOTE]
        ),
        patch("src.rag.explicador.retrieve", return_value=[]),
        patch("src.rag.explicador.curar", return_value=[]),
        patch("src.rag.explicador.get_client") as mock_client,
        caplog.at_level(logging.ERROR, logger="src.rag.explicador"),
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError(
            "API error"
        )
        explicar("O Livro dos Espíritos", "1")
    assert any("explicador" in r.message.lower() for r in caplog.records)
```

Add to `tests/test_curador.py` (match the file's existing import/mock style; the assertion is what matters):

```python
import logging
from unittest.mock import patch

from src.rag.curador import curar


def test_curar_logs_on_failure(caplog):
    candidates = [
        {"content": "x", "metadata": {"book": "B", "item_number": "1", "chapter_title": ""}}
    ]
    with (
        patch("src.rag.curador.get_client") as mock_client,
        caplog.at_level(logging.ERROR, logger="src.rag.curador"),
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError(
            "API error"
        )
        result = curar("texto principal", candidates)
    assert any("curador" in r.message.lower() for r in caplog.records)
    # fallback still returns the raw candidates
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generator.py::test_generate_logs_on_retrieval_error tests/test_reflect.py::test_reflect_logs_on_retrieval_error tests/test_explicador.py::test_explicar_logs_on_llm_error tests/test_curador.py::test_curar_logs_on_failure -v`
Expected: FAIL — no log records emitted yet.

- [ ] **Step 3: Add logging to `generator.py`**

At the top of `src/rag/generator.py`, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In the retrieval `except Exception:` block (the one returning `generation_failed=True`), add as its first line:

```python
        logger.exception("retrieve failed in /chat generate")
```

In the generation `except Exception:` block (where `answer = GENERATION_FAILED_MESSAGE`), add as its first line:

```python
        logger.exception("chat generation LLM call failed")
```

Before the `not_found` return (`if not chunks:` returning `not_found=True`), add:

```python
        logger.warning("no chunks retrieved for /chat; returning not_found")
```

Inside the book-fallback branch, after `fallback_note = BOOK_FALLBACK_NOTE.format(...)`, add:

```python
        logger.info("book_filter %s empty; fell back to full-collection search", book_filter)
```

- [ ] **Step 4: Add logging to `reflect.py`**

At the top of `src/rag/reflect.py`, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In the retrieval `except Exception:` block (returning `generation_failed=True`), add as its first line:

```python
        logger.exception("retrieve failed in /reflect")
```

In the `except Exception:` block around `reflexivo_future.result()` (where `generation_failed = True`), add as its first line:

```python
            logger.exception("reflexivo LLM call/parse failed")
```

Before the `not_found` return (`if not chunks:`), add:

```python
        logger.warning("no chunks retrieved for /reflect; returning not_found")
```

- [ ] **Step 5: Add logging to `explicador.py`**

At the top of `src/rag/explicador.py`, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In the related-items `except Exception:` block (`all_related = []`), add as its first line:

```python
        logger.exception("related-items retrieve failed in explicador")
```

In the `except Exception:` block around `explicador_future.result()` (`generation_failed = True`), add as its first line:

```python
            logger.exception("explicador LLM call/parse failed")
```

- [ ] **Step 6: Add logging to `curador.py`**

At the top of `src/rag/curador.py`, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In the `except Exception:` fallback block (where `curar` returns the raw candidates without `conexao`), add as its first line:

```python
        logger.exception("curador call/parse failed; falling back to raw candidates")
```

(If `curador.py` has more than one `except`, add the log line to the one guarding the LLM call + parse that produces the raw-candidate fallback. Read the file first to place it correctly.)

- [ ] **Step 7: Run the full suite to verify pass**

Run: `uv run pytest -v`
Expected: PASS — all new logging tests and every pre-existing test.

- [ ] **Step 8: Format and commit**

```bash
uv run isort src/ tests/ && uv run black src/ tests/
git add src/rag/generator.py src/rag/reflect.py src/rag/explicador.py src/rag/curador.py tests/
git commit -m "feat: add failure-path logging across RAG pipelines

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Refletir routing button (A4 frontend)

**Files:**
- Modify: `frontend/src/App.jsx` (add `handleGoReflect`; render button; pass source question in the `msgs.map`)

**Interfaces:**
- Consumes: backend `suggested_mode: "refletir"` from Task 4, surfaced by `mapChat` as `msg.suggestedMode` (already mapped at `frontend/src/services/api.js:52` — no change needed there).
- Produces: a new button under `/chat` answers whose `suggestedMode === 'refletir'`.

> **No automated test:** the frontend has no test harness (no vitest/jest). This task is verified manually (Step 4). Do not add a test framework — that is out of scope for Batch A.

- [ ] **Step 1: Add the `handleGoReflect` handler**

In `frontend/src/App.jsx`, add this handler near `handleGoStudyItem` (after it, around line 480). It deliberately does **not** route through `sendText` — `sendText` captures a stale `mode` in its closure and would misroute to `/chat`. It calls `reflectSituation` (mode-independent) directly:

```jsx
  // ── Suggested-mode: jump from /chat to a Refletir thread seeded with the question ──
  const handleGoReflect = async (situationText) => {
    if (!situationText) return;
    switchMode('refletir');
    setRefletirSub('chat');
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: situationText };
    setMsgs([userMsg]); setLoading(true);
    const id = 'c' + Date.now();
    setConvoId(id);
    saveConvo(id, situationText.slice(0, 48), 'refletir', [userMsg]);
    scrollToBottom();
    const requestId = ++requestIdRef.current;
    try {
      const reply = await reflectSituation(situationText, []);
      if (requestId !== requestIdRef.current) return;
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [userMsg, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, situationText.slice(0, 48), 'refletir', finalMsgs);
    } catch (err) {
      console.error('handleGoReflect failed:', err);
      if (requestId !== requestIdRef.current) return;
      setMsgs([userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        scrollToBottom();
      }
    }
  };
```

- [ ] **Step 2: Pass the source question into the message map and render the button**

In `frontend/src/App.jsx`, change the message map opening from:

```jsx
                {msgs.map(msg => (
```

to:

```jsx
                {msgs.map((msg, idx) => (
```

Then, inside the `<AIMessage ...>` children (immediately after the existing `msg.suggestedMode === 'estudar_obra'` block that ends around line 820), add the refletir button block:

```jsx
                        {msg.suggestedMode === 'refletir' && (() => {
                          const srcQuestion = msgs
                            .slice(0, idx).reverse().find(m => m.isUser)?.text;
                          return srcQuestion ? (
                            <div style={{ marginTop: 10 }}>
                              <button
                                onClick={() => handleGoReflect(srcQuestion)}
                                style={{
                                  background: 'transparent', border: '1px solid rgba(200,133,106,.4)',
                                  color: '#C8856A', padding: '7px 14px', borderRadius: 8,
                                  fontSize: 13, fontWeight: 500, cursor: 'pointer',
                                  display: 'flex', alignItems: 'center', gap: 6,
                                }}
                              >
                                🪞 Refletir sobre esta situação
                              </button>
                            </div>
                          ) : null;
                        })()}
```

- [ ] **Step 3: Start the app**

```bash
# Terminal 1 (from repo root)
uv run fastapi dev src/api/main.py
# Terminal 2
cd frontend && npm run dev
```

Expected: API on `http://localhost:8000`, frontend on `http://localhost:5173`, no console/build errors.

- [ ] **Step 4: Manually verify the button end-to-end**

In the browser (Tirar uma Dúvida / "duvida" mode):
1. Type `tenho medo de morrer` and send.
2. Confirm a `/chat` answer renders, followed by a terracotta-outlined **🪞 Refletir sobre esta situação** button.
3. Click it. Confirm the view switches to Refletir mode and opens a reflection thread (empathetic opening + doctrine connection + 3 reflection-question buttons) seeded with "tenho medo de morrer".
4. Type a plainly factual question (`o que é reencarnação?`) and confirm the refletir button does **not** appear.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: add Refletir routing button for situational chat answers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** A1 → Tasks 1-2; A2 → Task 3; A3 → Task 5; A4 backend → Task 4, A4 frontend → Task 6. All spec sections covered.
- **Type consistency:** `condense_query(question, history)` signature identical across Tasks 1-2 and both call sites. `detect_suggested_mode` return set `{"estudar_obra","refletir",None}` consistent between Task 4 and the existing `mapChat`/`App.jsx` consumers.
- **Mode-timing hazard (spec-flagged):** resolved in Task 6 Step 1 by bypassing `sendText` and calling `reflectSituation` directly.
- **No frontend test harness:** Task 6 uses manual verification by design; the spec's "lightweight render/click test … if present" resolves to manual since none is present.
