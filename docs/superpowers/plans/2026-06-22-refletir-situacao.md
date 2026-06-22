# Refletir sobre uma Situação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /reflect` — a mode that receives a personal life situation and returns what Kardec's doctrine says about it, three reflection questions, and complementary readings, with tone-adaptive empathy and a hard no-advice constraint.

**Architecture:** Single retrieval call fetches top 5 semantically matched chunks; first 2 become primary sources and feed the LLM; chunks 3–5 become complementary items. One LLM call with an educator prompt that is forbidden from giving advice, calibrates tone from the situation text, and optionally appends a medical-professional caveat when clinical/mediumistic keywords are detected.

**Tech Stack:** Python 3.12, FastAPI, ChromaDB, sentence-transformers, OpenAI-compatible client (Groq), Pydantic v2, uv.

## Global Constraints

- All commands: `uv run <cmd>` (e.g., `uv run pytest`)
- No LLM calls in tests — always mock `_get_client()` and `retrieve()`
- All user-facing strings and prompts in Portuguese (Brasil)
- Hard no-advice rule verbatim in system prompt: never "você deveria", "recomendo", "tente", "considere", medication, donation, separation, or behavior changes
- `not_found` is returned as `True` in the response body (200 status); no 404 for this endpoint
- `generation_failed: True` when LLM call throws — `opening` and `doctrine_connection` are `""`, `reflection_questions` is `[]`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `src/rag/reflect_prompt.py` | Keyword detection, system prompt builder, JSON parser |
| Create | `src/rag/reflect.py` | Orchestrate retrieve → caveat check → LLM → structured result |
| Modify | `src/api/schemas.py` | Add `ReflectRequest`, `ReflectResponse` |
| Modify | `src/api/routes.py` | Add `POST /reflect` |
| Create | `tests/test_reflect_prompt.py` | Tests for keyword detection, prompt builder, parser |
| Create | `tests/test_reflect.py` | Tests for `reflect()` function |
| Modify | `tests/test_api.py` | Add reflect endpoint tests |

**Reused models (no new types needed):** `RelatedItem` (same `{book, item_number, preview}` shape) and `StudySource` (same `{book, chapter_title?, item_number}` shape) already exist in `schemas.py`.

---

### Task 1: reflect_prompt.py

**Files:**
- Create: `src/rag/reflect_prompt.py`
- Create: `tests/test_reflect_prompt.py`

**Interfaces:**
- Produces: `CLINICAL_KEYWORDS: list[str]`
- Produces: `needs_medical_caveat(situation: str) -> bool`
- Produces: `build_reflect_messages(situation: str, chunks: list[dict], add_caveat: bool) -> tuple[str, list[dict]]`
- Produces: `parse_reflect_json(text: str) -> tuple[str, str, list[str]]` — `(opening, doctrine_connection, reflection_questions)`

- [ ] **Step 1: Create `tests/test_reflect_prompt.py` with failing tests**

```python
from src.rag.reflect_prompt import (
    build_reflect_messages,
    needs_medical_caveat,
    parse_reflect_json,
)

_CHUNK = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {"book": "O Livro dos Espíritos", "item_number": "150"},
    "distance": 0.3,
}


def test_needs_medical_caveat_true_for_vozes():
    assert needs_medical_caveat("escuto vozes à noite") is True


def test_needs_medical_caveat_true_for_sombras():
    assert needs_medical_caveat("estou vendo sombras") is True


def test_needs_medical_caveat_false_for_normal_situation():
    assert needs_medical_caveat("meu pai faleceu") is False


def test_caveat_instruction_in_system_when_needed():
    system, _ = build_reflect_messages("escuto vozes", [], add_caveat=True)
    assert "profissional de saúde" in system


def test_no_caveat_in_system_when_not_needed():
    system, _ = build_reflect_messages("meu pai faleceu", [], add_caveat=False)
    assert "profissional de saúde" not in system


def test_no_advice_constraint_in_system():
    system, _ = build_reflect_messages("qualquer situação", [], add_caveat=False)
    assert "absolutamente proibido" in system


def test_situation_text_appears_in_system():
    system, _ = build_reflect_messages("meu casamento está difícil", [], add_caveat=False)
    assert "meu casamento está difícil" in system


def test_chunk_content_appears_in_system():
    system, _ = build_reflect_messages("situação", [_CHUNK], add_caveat=False)
    assert "Os espíritos sobrevivem" in system


def test_messages_contains_single_user_message():
    _, messages = build_reflect_messages("situação", [], add_caveat=False)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


def test_parse_reflect_json_extracts_all_fields():
    text = '{"opening": "Sentimos sua dor.", "doctrine_connection": "A doutrina diz...", "reflection_questions": ["Q1?", "Q2?", "Q3?"]}'
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "Sentimos sua dor."
    assert conn == "A doutrina diz..."
    assert questions == ["Q1?", "Q2?", "Q3?"]


def test_parse_reflect_json_strips_markdown_fences():
    text = '```json\n{"opening": "A.", "doctrine_connection": "B.", "reflection_questions": ["C?"]}\n```'
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "A."
    assert conn == "B."
    assert questions == ["C?"]


def test_parse_reflect_json_falls_back_on_invalid_json():
    text = "não é JSON válido"
    opening, conn, questions = parse_reflect_json(text)
    assert opening == "não é JSON válido"
    assert conn == ""
    assert questions == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_reflect_prompt.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.reflect_prompt'`

- [ ] **Step 3: Create `src/rag/reflect_prompt.py`**

```python
import json
import re

CLINICAL_KEYWORDS = [
    "vozes",
    "sombras",
    "escuto",
    "vejo entidades",
    "ouço",
    "pânico",
    "desespero",
    "não consigo dormir",
    "alucinação",
]

_NO_ADVICE = """\
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria", \
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação, \
doação, separação, mudança de comportamento, ou qualquer outro curso de ação. \
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para \
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados."""

_CAVEAT_INSTRUCTION = """\
Se a situação descrita puder ter causas clínicas, acrescente UMA frase curta \
ao final indicando que o apoio de um profissional de saúde é também valioso — \
sem substituir a visão espírita e sem fazer diagnósticos."""

_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos espíritas que ajuda pessoas a verem situações \
da vida através da doutrina de Allan Kardec. Baseando-se SOMENTE nos trechos \
abaixo, retorne APENAS um JSON válido com as chaves exatas:
{{
  "opening": "<abertura empática ou alegre conforme o peso emocional da situação>",
  "doctrine_connection": "<o que a doutrina diz e como se conecta à situação descrita>",
  "reflection_questions": ["<pergunta 1>", "<pergunta 2>", "<pergunta 3>"]
}}

Regras de tom:
- Se a situação envolve perda, dor, medo ou dificuldade → abra com empatia e acolhimento.
- Se a situação é positiva (nascimento, gratidão, celebração) → abra com calor e alegria.
- Caso ambíguo → abra com compaixão equilibrada.

{no_advice}

{caveat}

[SITUAÇÃO DO USUÁRIO]
{situation}

[PASSAGENS RECUPERADAS]
{passages}"""


def needs_medical_caveat(situation: str) -> bool:
    lower = situation.lower()
    return any(kw in lower for kw in CLINICAL_KEYWORDS)


def _format_passages(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma passagem encontrada)"
    parts = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = f"[{i}] {m['book']}"
        if m.get("item_number"):
            header += f" | Item {m['item_number']}"
        parts.append(f"{header}\n\"{c['content']}\"")
    return "\n\n".join(parts)


def build_reflect_messages(
    situation: str, chunks: list[dict], add_caveat: bool
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        no_advice=_NO_ADVICE,
        caveat=_CAVEAT_INSTRUCTION if add_caveat else "",
        situation=situation,
        passages=_format_passages(chunks),
    )
    messages = [{"role": "user", "content": "Veja essa situação pela lente da doutrina espírita."}]
    return system, messages


def parse_reflect_json(text: str) -> tuple[str, str, list[str]]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()
    try:
        data = json.loads(text)
        return (
            data.get("opening", ""),
            data.get("doctrine_connection", ""),
            data.get("reflection_questions", []),
        )
    except (json.JSONDecodeError, AttributeError):
        return text, "", []
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_reflect_prompt.py -v
```

Expected: all 12 tests PASS

- [ ] **Step 5: Run the full suite to confirm no regressions**

```
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/rag/reflect_prompt.py tests/test_reflect_prompt.py
git commit -m "feat: add reflect prompt builder, keyword caveat detection, and JSON parser"
```

---

### Task 2: reflect.py

**Files:**
- Create: `src/rag/reflect.py`
- Create: `tests/test_reflect.py`

**Interfaces:**
- Consumes: `retrieve(query: str, top_k: int | None = None) -> list[dict]` from `src.rag.retriever`
- Consumes: `build_reflect_messages`, `needs_medical_caveat`, `parse_reflect_json` from Task 1
- Produces: `reflect(situation: str) -> dict`
  - Always returns a dict (never None)
  - Keys: `opening: str`, `doctrine_connection: str`, `reflection_questions: list[str]`, `complementary_items: list[dict]`, `sources: list[dict]`, `not_found: bool`, `generation_failed: bool`
  - `sources` items: `{book, chapter_title, item_number}`
  - `complementary_items` items: `{book, item_number, preview}` where `preview = content[:200]`

- [ ] **Step 1: Create `tests/test_reflect.py` with failing tests**

```python
from unittest.mock import MagicMock, patch

from src.rag.reflect import reflect

_CHUNK_1 = {
    "content": "Os espíritos sobrevivem à morte do corpo.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "150",
        "chapter_title": "Da Alma",
    },
    "distance": 0.3,
}
_CHUNK_2 = {
    "content": "A angústia é uma prova da alma.",
    "metadata": {
        "book": "O Livro dos Espíritos",
        "item_number": "132",
        "chapter_title": "Da Encarnação",
    },
    "distance": 0.5,
}
_CHUNK_3 = {
    "content": "O amor é a lei suprema.",
    "metadata": {
        "book": "O Evangelho segundo o Espiritismo",
        "item_number": "section-1",
        "chapter_title": "",
    },
    "distance": 0.7,
}

_LLM_JSON = '{"opening": "Compreendemos sua dor.", "doctrine_connection": "A doutrina ensina...", "reflection_questions": ["Q1?", "Q2?", "Q3?"]}'


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def test_reflect_returns_not_found_when_no_chunks():
    with patch("src.rag.reflect.retrieve", return_value=[]):
        result = reflect("meu pai faleceu")
    assert result["not_found"] is True
    assert result["generation_failed"] is False
    assert result["opening"] == ""
    assert result["complementary_items"] == []
    assert result["sources"] == []


def test_reflect_returns_opening_from_llm():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("meu pai faleceu")
    assert result["opening"] == "Compreendemos sua dor."
    assert result["not_found"] is False


def test_reflect_returns_reflection_questions():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("meu pai faleceu")
    assert result["reflection_questions"] == ["Q1?", "Q2?", "Q3?"]


def test_reflect_sets_generation_failed_on_llm_error():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.side_effect = RuntimeError("API error")
        result = reflect("situação")
    assert result["generation_failed"] is True
    assert result["opening"] == ""
    assert result["not_found"] is False


def test_reflect_sources_come_from_first_two_chunks():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2, _CHUNK_3]),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("situação")
    assert len(result["sources"]) == 2
    item_numbers = [s["item_number"] for s in result["sources"]]
    assert "150" in item_numbers
    assert "132" in item_numbers


def test_reflect_complementary_items_come_from_chunks_3_to_5():
    extra = [
        {
            "content": f"texto {i}",
            "metadata": {"book": "Livro X", "item_number": str(i), "chapter_title": ""},
            "distance": 0.9,
        }
        for i in range(3, 6)
    ]
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1, _CHUNK_2] + extra),
        patch("src.rag.reflect._get_client") as mock_client,
    ):
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        result = reflect("situação")
    assert len(result["complementary_items"]) == 3
    assert result["complementary_items"][0]["item_number"] == "3"


def test_reflect_passes_add_caveat_true_for_clinical_keywords():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        reflect("escuto vozes à noite")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is True


def test_reflect_passes_add_caveat_false_for_normal_situation():
    with (
        patch("src.rag.reflect.retrieve", return_value=[_CHUNK_1]),
        patch("src.rag.reflect._get_client") as mock_client,
        patch("src.rag.reflect.build_reflect_messages") as mock_build,
    ):
        mock_build.return_value = ("system", [{"role": "user", "content": "msg"}])
        mock_client.return_value.chat.completions.create.return_value = _make_llm_response(_LLM_JSON)
        reflect("meu pai faleceu")
    _, _, add_caveat = mock_build.call_args[0]
    assert add_caveat is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_reflect.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.reflect'`

- [ ] **Step 3: Create `src/rag/reflect.py`**

```python
from openai import OpenAI

from src.core.config import settings
from src.rag.reflect_prompt import build_reflect_messages, needs_medical_caveat, parse_reflect_json
from src.rag.retriever import retrieve

_NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec passagens suficientemente relacionadas "
    "à situação descrita."
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def reflect(situation: str) -> dict:
    chunks = retrieve(situation, top_k=5)

    if not chunks:
        return {
            "opening": "",
            "doctrine_connection": _NOT_FOUND_MESSAGE,
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": True,
            "generation_failed": False,
        }

    primary = chunks[:2]
    complementary_raw = chunks[2:5]

    add_caveat = needs_medical_caveat(situation)
    system, messages = build_reflect_messages(situation, primary, add_caveat)

    opening = ""
    doctrine_connection = ""
    reflection_questions = []
    generation_failed = False
    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        opening, doctrine_connection, reflection_questions = parse_reflect_json(
            response.choices[0].message.content
        )
    except Exception:
        generation_failed = True

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in primary
    ]

    complementary_items = [
        {
            "book": c["metadata"]["book"],
            "item_number": c["metadata"]["item_number"],
            "preview": c["content"][:200],
        }
        for c in complementary_raw
    ]

    return {
        "opening": opening,
        "doctrine_connection": doctrine_connection,
        "reflection_questions": reflection_questions,
        "complementary_items": complementary_items,
        "sources": sources,
        "not_found": False,
        "generation_failed": generation_failed,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_reflect.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Run the full suite to confirm no regressions**

```
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/rag/reflect.py tests/test_reflect.py
git commit -m "feat: add reflect generator with caveat detection and not-found handling"
```

---

### Task 3: Schemas + Route + API tests

**Files:**
- Modify: `src/api/schemas.py`
- Modify: `src/api/routes.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `reflect(situation: str) -> dict` from Task 2 — imported as `reflect as reflect_fn` to avoid name collision with the route function
- Reuses existing: `RelatedItem` (for `complementary_items`), `StudySource` (for `sources`) — already in schemas.py
- New schemas: `ReflectRequest`, `ReflectResponse`

- [ ] **Step 1: Write failing API tests**

Add to the bottom of `tests/test_api.py`:

```python
_REFLECT_RESULT = {
    "opening": "Compreendemos profundamente sua dor.",
    "doctrine_connection": "A doutrina espírita ensina que a morte não é o fim.",
    "reflection_questions": [
        "O que essa situação revela sobre minha jornada espiritual?",
        "Como a perspectiva da continuidade da vida muda meu sentimento?",
        "Que mensagem meu pai poderia me transmitir agora?",
    ],
    "complementary_items": [],
    "sources": [
        {"book": "O Livro dos Espíritos", "chapter_title": "Da Alma", "item_number": "150"}
    ],
    "not_found": False,
    "generation_failed": False,
}

_REFLECT_NOT_FOUND = {
    "opening": "",
    "doctrine_connection": "Não encontrei passagens relacionadas.",
    "reflection_questions": [],
    "complementary_items": [],
    "sources": [],
    "not_found": True,
    "generation_failed": False,
}


def test_reflect_returns_200():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        response = client.post("/reflect", json={"situation": "meu pai faleceu"})
    assert response.status_code == 200
    data = response.json()
    assert data["opening"] == "Compreendemos profundamente sua dor."
    assert len(data["reflection_questions"]) == 3
    assert data["not_found"] is False


def test_reflect_returns_200_with_not_found_flag_when_no_doctrine():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_NOT_FOUND):
        response = client.post("/reflect", json={"situation": "assunto sem doutrina"})
    assert response.status_code == 200
    assert response.json()["not_found"] is True


def test_reflect_response_has_all_required_fields():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        data = client.post("/reflect", json={"situation": "meu casamento está difícil"}).json()
    for field in ("opening", "doctrine_connection", "reflection_questions", "complementary_items", "sources", "not_found", "generation_failed"):
        assert field in data


def test_reflect_passes_situation_to_reflect_fn():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT) as mock_fn:
        client.post("/reflect", json={"situation": "me sinto vazio"})
    mock_fn.assert_called_once_with("me sinto vazio")
```

- [ ] **Step 2: Run new tests to verify they fail**

```
uv run pytest tests/test_api.py::test_reflect_returns_200 tests/test_api.py::test_reflect_returns_200_with_not_found_flag_when_no_doctrine -v
```

Expected: failures — route and schema don't exist yet

- [ ] **Step 3: Add `ReflectRequest` and `ReflectResponse` to `src/api/schemas.py`**

Add after the `StudyResponse` class (end of file):

```python
class ReflectRequest(BaseModel):
    situation: str
    conversation_history: list[Message] = []


class ReflectResponse(BaseModel):
    opening: str
    doctrine_connection: str
    reflection_questions: list[str]
    complementary_items: list[RelatedItem]
    sources: list[StudySource]
    not_found: bool = False
    generation_failed: bool = False
```

- [ ] **Step 4: Add the `/reflect` route to `src/api/routes.py`**

Add to the imports block at the top:

```python
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    PathDetail,
    PathSummary,
    ReflectRequest,
    ReflectResponse,
    Source,
    StudyRequest,
    StudyResponse,
)
from src.rag.reflect import reflect as reflect_fn
```

Add the route function before `@router.get("/health")`:

```python
@router.post("/reflect", response_model=ReflectResponse)
def reflect_situation(request: ReflectRequest) -> ReflectResponse:
    result = reflect_fn(request.situation)
    return ReflectResponse(**result)
```

- [ ] **Step 5: Run all API tests to verify they pass**

```
uv run pytest tests/test_api.py -v
```

Expected: all tests PASS (12 existing + 4 new = 16 total)

- [ ] **Step 6: Run the full suite to confirm no regressions**

```
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/schemas.py src/api/routes.py tests/test_api.py
git commit -m "feat: add /reflect endpoint with ReflectRequest and ReflectResponse schemas"
```
