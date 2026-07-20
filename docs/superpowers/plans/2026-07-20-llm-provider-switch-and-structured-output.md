# LLM Provider Switch + Structured JSON Output — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator select the LLM provider (Groq / OpenRouter / Together AI) with one env var, reusing the existing OpenAI-compatible client, and add schema-enforced JSON output to the three JSON-producing calls with graceful fallback.

**Architecture:** A static provider registry in `config.py` maps a `LLM_PROVIDER` key to its `base_url`, API-key field, and default model names; resolution properties pick the active provider and let explicit `CHAT_MODEL`/`CONDENSER_MODEL` env vars override the defaults. `llm_client.py` builds the `OpenAI` client from the active provider and exposes `create_json_completion()`, which adds `response_format={"type": "json_object"}` and retries once without it if the provider rejects the param. The three JSON call sites (`sensitivity`, `orchestrator`, `reflect`) route through the helper; their existing regex extraction stays as the parse layer. `/chat`'s trailer-marker contract is untouched.

**Tech Stack:** Python 3.12, pydantic-settings, `openai` SDK (OpenAI-compatible), pytest, uv.

## Global Constraints

- Default `LLM_PROVIDER=groq` — absent any new env vars, behavior is **identical to today** (backward compatible).
- Package manager is **uv**: run tests with `uv run pytest`.
- Spec of record: `docs/superpowers/specs/2026-07-20-llm-provider-switch-and-structured-output-design.md`.
- Do **not** change `/chat`'s `[FONTES]`/`[SEGUIR]` trailer-marker contract or `query_condenser` (returns a plain string, not JSON).
- The full existing test suite (373 tests) must stay green after every task.
- Commit messages end with the repo's `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

### Task 1: Provider registry + config resolution

**Files:**
- Modify: `src/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `ProviderConfig` NamedTuple: `(base_url: str, api_key_field: str, default_chat_model: str, default_condenser_model: str)`
  - `PROVIDERS: dict[str, ProviderConfig]` with keys `"groq"`, `"openrouter"`, `"together"`
  - `Settings` new fields: `llm_provider: str = "groq"`, `openrouter_api_key: str | None`, `together_api_key: str | None`, `chat_model: str | None = None`, `condenser_model: str | None = None`, `structured_output: bool = True`; `groq_api_key` becomes `str | None = None`
  - `Settings` properties: `active_provider -> ProviderConfig`, `active_api_key -> str`, `resolved_chat_model -> str`, `resolved_condenser_model -> str`

- [ ] **Step 1: Write the failing tests**

Replace the two existing tests in `tests/test_config.py` that assert the old hardcoded `chat_model`/`condenser_model` and the `ValidationError`-on-missing-key behavior (both change under this design), and add resolution tests:

```python
import pytest


def _settings(monkeypatch, **env):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.delenv("CONDENSER_MODEL", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from src.core.config import Settings

    return Settings(_env_file=None)


def test_defaults_to_groq_provider(monkeypatch):
    s = _settings(monkeypatch, GROQ_API_KEY="k")
    assert s.llm_provider == "groq"
    assert s.active_provider.base_url == "https://api.groq.com/openai/v1"
    assert s.active_api_key == "k"
    assert s.resolved_chat_model == "llama-3.3-70b-versatile"
    assert s.resolved_condenser_model == "llama-3.1-8b-instant"


def test_openrouter_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="or-k")
    assert s.active_provider.base_url == "https://openrouter.ai/api/v1"
    assert s.active_api_key == "or-k"
    assert s.resolved_chat_model == "deepseek/deepseek-chat"


def test_together_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="together", TOGETHER_API_KEY="tg-k")
    assert s.active_provider.base_url == "https://api.together.xyz/v1"
    assert s.resolved_chat_model == "deepseek-ai/DeepSeek-V3"


def test_explicit_model_overrides_provider_default(monkeypatch):
    s = _settings(
        monkeypatch,
        LLM_PROVIDER="together",
        TOGETHER_API_KEY="tg-k",
        CHAT_MODEL="my/custom-model",
    )
    assert s.resolved_chat_model == "my/custom-model"


def test_unknown_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="bogus", GROQ_API_KEY="k")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        _ = s.active_provider


def test_missing_key_for_selected_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter")  # no OPENROUTER_API_KEY
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        _ = s.active_api_key
```

Keep the unchanged `test_settings_has_correct_defaults` assertions that still hold (`top_k`, `max_distance`, `max_history_turns`, `chroma_collection`, `paths_dir`, `embedding_model`); **remove** its two lines asserting `s.chat_model == "llama-3.3-70b-versatile"` and `s.condenser_model == "llama-3.1-8b-instant"` (those fields now default to `None`; the resolved-model tests above cover the values). **Remove** `test_settings_requires_api_key` (missing key no longer fails at construction; `test_missing_key_for_selected_provider_raises` replaces it).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: the new tests FAIL with `AttributeError` (no `active_provider` / `resolved_chat_model`).

- [ ] **Step 3: Implement the registry and resolution**

Rewrite `src/core/config.py`:

```python
from typing import NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(NamedTuple):
    base_url: str
    api_key_field: str
    default_chat_model: str
    default_condenser_model: str


PROVIDERS: dict[str, ProviderConfig] = {
    "groq": ProviderConfig(
        "https://api.groq.com/openai/v1",
        "groq_api_key",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ),
    "openrouter": ProviderConfig(
        "https://openrouter.ai/api/v1",
        "openrouter_api_key",
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.1-8b-instruct",
    ),
    "together": ProviderConfig(
        "https://api.together.xyz/v1",
        "together_api_key",
        "deepseek-ai/DeepSeek-V3",
        "meta-llama/Llama-3.1-8B-Instruct-Turbo",
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = "groq"
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    together_api_key: str | None = None
    hf_token: str | None = None

    # Optional per-model overrides; unset → the active provider's default.
    chat_model: str | None = None
    condenser_model: str | None = None
    structured_output: bool = True

    embedding_model: str = "BAAI/bge-m3"
    top_k: int = 5
    max_distance: float = 0.55
    max_history_turns: int = 10
    chroma_path: str = "data/embeddings/"
    chroma_collection: str = "kardec_docs"
    json_dir: str = "data/json_files"
    paths_dir: str = "data/paths"
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def active_provider(self) -> ProviderConfig:
        try:
            return PROVIDERS[self.llm_provider]
        except KeyError:
            raise ValueError(
                f"Unknown LLM_PROVIDER {self.llm_provider!r}; "
                f"valid options: {', '.join(PROVIDERS)}"
            )

    @property
    def active_api_key(self) -> str:
        field = self.active_provider.api_key_field
        key = getattr(self, field)
        if not key:
            raise ValueError(
                f"LLM_PROVIDER={self.llm_provider!r} requires "
                f"{field.upper()} to be set in the environment/.env"
            )
        return key

    @property
    def resolved_chat_model(self) -> str:
        return self.chat_model or self.active_provider.default_chat_model

    @property
    def resolved_condenser_model(self) -> str:
        return self.condenser_model or self.active_provider.default_condenser_model


settings = Settings()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/test_config.py
git commit -m "feat(config): provider registry + LLM_PROVIDER resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Client construction from active provider + `create_json_completion` helper

**Files:**
- Modify: `src/rag/llm_client.py`
- Test: `tests/test_llm_client.py` (create)

**Interfaces:**
- Consumes: `settings.active_provider`, `settings.active_api_key`, `settings.structured_output` (Task 1)
- Produces:
  - `get_client() -> OpenAI` (unchanged signature; now built from the active provider)
  - `create_json_completion(client, model, messages, max_tokens, structured=None)` — calls `client.chat.completions.create(...)` with `response_format={"type": "json_object"}` when `structured` (defaults to `settings.structured_output`); on `openai.BadRequestError` retries once **without** `response_format`; returns the completion object.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_client.py`:

```python
from unittest.mock import MagicMock

import httpx
import openai

from src.rag.llm_client import create_json_completion

_MSGS = [{"role": "user", "content": "hi"}]


def _client_returning(response):
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


def test_structured_true_passes_response_format():
    resp = MagicMock()
    client = _client_returning(resp)
    out = create_json_completion(client, "m", _MSGS, 30, structured=True)
    assert out is resp
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_structured_false_omits_response_format():
    resp = MagicMock()
    client = _client_returning(resp)
    create_json_completion(client, "m", _MSGS, 30, structured=False)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


def test_retries_without_response_format_on_bad_request():
    resp_ok = MagicMock()
    req = httpx.Request("POST", "http://x")
    http_resp = httpx.Response(400, request=req)
    bad = openai.BadRequestError("response_format unsupported", response=http_resp, body=None)

    client = MagicMock()
    client.chat.completions.create.side_effect = [bad, resp_ok]

    out = create_json_completion(client, "m", _MSGS, 30, structured=True)
    assert out is resp_ok
    assert client.chat.completions.create.call_count == 2
    # second (successful) call must NOT carry response_format
    second_kwargs = client.chat.completions.create.call_args_list[1].kwargs
    assert "response_format" not in second_kwargs
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'create_json_completion'`.

- [ ] **Step 3: Implement client + helper**

Rewrite `src/rag/llm_client.py`:

```python
from openai import BadRequestError, OpenAI

from src.core.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        provider = settings.active_provider
        _client = OpenAI(
            api_key=settings.active_api_key,
            base_url=provider.base_url,
        )
    return _client


def create_json_completion(client, model, messages, max_tokens, structured=None):
    """Chat completion whose output is expected to be JSON. Adds
    response_format=json_object when structured output is enabled, and retries
    once WITHOUT it if the provider/model rejects the parameter. Callers still
    parse the returned content themselves (their existing regex extraction)."""
    if structured is None:
        structured = settings.structured_output
    if structured:
        try:
            return client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                response_format={"type": "json_object"},
            )
        except BadRequestError:
            pass
    return client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/rag/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): build client from active provider + create_json_completion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Route JSON calls through the helper + use resolved model names everywhere

**Files:**
- Modify: `src/rag/sensitivity.py`, `src/rag/orchestrator.py`, `src/rag/reflect.py`
- Modify (model reference only): `src/rag/explicador.py`, `src/rag/curador.py`, `src/rag/generator.py`, `src/rag/generate_chapter_summaries.py`, `src/rag/query_condenser.py`
- Test: existing `tests/test_sensitivity.py`, `tests/test_orchestrator.py`, `tests/test_reflect.py` (must stay green); add one assertion to `tests/test_sensitivity.py`

**Interfaces:**
- Consumes: `create_json_completion` (Task 2), `settings.resolved_chat_model`, `settings.resolved_condenser_model` (Task 1)
- Produces: no new public symbols — internal wiring only.

- [ ] **Step 1: Add a test asserting the JSON path uses the helper**

Append to `tests/test_sensitivity.py`:

```python
def test_classify_uses_json_response_format(monkeypatch):
    from unittest.mock import MagicMock

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content='{"nivel": "normal"}'))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.sensitivity.get_client", lambda: client)
    monkeypatch.setattr("src.core.config.settings.structured_output", True)

    classify_sensitivity("o que é o perispírito?")
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_sensitivity.py::test_classify_uses_json_response_format -v`
Expected: FAIL — current code calls `create` without `response_format`.

- [ ] **Step 3: Route `sensitivity.py` through the helper**

In `src/rag/sensitivity.py`, change the import and the call. Import line:

```python
from src.rag.llm_client import create_json_completion, get_client
```

Replace the `response = get_client().chat.completions.create(...)` block inside `classify_sensitivity` with:

```python
        response = create_json_completion(
            get_client(),
            model=settings.resolved_condenser_model,
            max_tokens=30,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
```

- [ ] **Step 4: Route `orchestrator.py` through the helper**

In `src/rag/orchestrator.py`, add `create_json_completion` to the `llm_client` import, and replace the `response = get_client().chat.completions.create(...)` block inside `classify_intent` with:

```python
        response = create_json_completion(
            get_client(),
            model=settings.resolved_condenser_model,
            max_tokens=60,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_content(message, history)},
            ],
        )
```

- [ ] **Step 5: Route `reflect.py` through the helper**

In `src/rag/reflect.py`, add `create_json_completion` to the `llm_client` import, and replace the body of `_call_reflexivo` with:

```python
    def _call_reflexivo():
        response = create_json_completion(
            get_client(),
            model=settings.resolved_chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return parse_reflect_json(response.choices[0].message.content)
```

- [ ] **Step 6: Swap remaining model references to resolved properties**

These call sites keep their direct `create(...)` (they are not JSON-object calls) but must use the resolved model names so a provider switch reaches them. In each, replace `settings.chat_model` → `settings.resolved_chat_model` and `settings.condenser_model` → `settings.resolved_condenser_model`:

- `src/rag/explicador.py` (`model=settings.chat_model`)
- `src/rag/curador.py` (`model=settings.chat_model`)
- `src/rag/generator.py` (`model=settings.chat_model`)
- `src/rag/generate_chapter_summaries.py` (`model=settings.chat_model`)
- `src/rag/query_condenser.py` (`model=settings.condenser_model`)

- [ ] **Step 7: Run the affected + full suite**

Run: `uv run pytest tests/test_sensitivity.py tests/test_orchestrator.py tests/test_reflect.py -v`
Expected: PASS, including `test_classify_uses_json_response_format`.

Then the full suite:

Run: `uv run pytest`
Expected: all green (373 + the new tests).

- [ ] **Step 8: Commit**

```bash
git add src/rag/sensitivity.py src/rag/orchestrator.py src/rag/reflect.py \
        src/rag/explicador.py src/rag/curador.py src/rag/generator.py \
        src/rag/generate_chapter_summaries.py src/rag/query_condenser.py \
        tests/test_sensitivity.py
git commit -m "feat(rag): resolved models everywhere; JSON calls use response_format

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Live acceptance across providers (manual)

**Files:** none (uses `scripts/probe_backend.py`).

This task has no automated deliverable — it is the cross-provider scorecard from the spec. Run it once the code tasks are green and you have keys.

- [ ] **Step 1: Baseline on Groq**

```bash
# .env: LLM_PROVIDER=groq (default), GROQ_API_KEY set
uv run fastapi dev src/api/main.py --port 8000   # in one shell
uv run python scripts/probe_backend.py --base http://localhost:8000
```
Expected: matches the current baseline (40 PASS; C4 a WARN heuristic).

- [ ] **Step 2: OpenRouter**

Set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY=...` in `.env`, restart the server, rerun the probe. Expected: a **complete Group G run** (no rate-limit WARNs). Note any contract FAILs (D1 markers, reflect JSON) — those tell you whether DeepSeek-V3 honors the contracts.

- [ ] **Step 3: Together**

Set `LLM_PROVIDER=together` and `TOGETHER_API_KEY=...`, restart, rerun. Compare the PASS/WARN/FAIL profile against the Groq baseline and OpenRouter.

- [ ] **Step 4: Record the winner**

Whichever provider/model best holds the 40 checks becomes the recommended default; set it in `.env`. No code change needed (model is env-overridable).

---

## Self-Review

**Spec coverage:**
- Provider registry (spec §1) → Task 1. ✅
- Config resolution + override precedence + clear errors (spec §2, §5) → Task 1. ✅
- Client from active provider (spec §3) → Task 2. ✅
- `create_json_completion` + fallback (spec §4) → Task 2; call-site routing → Task 3. ✅
- `query_condenser`/`/chat` explicitly excluded from the helper (spec §4) → Task 3 Step 6 keeps `query_condenser` on a direct call; `/chat` generator untouched. ✅
- Testing: unit (Tasks 1–3) + live acceptance (Task 4) (spec Testing). ✅
- Backward compatibility default groq (spec Rollout) → Task 1 default + Global Constraints. ✅

**Placeholder scan:** none — every code/test step contains full code and exact commands.

**Type consistency:** `ProviderConfig` fields and `PROVIDERS` keys defined in Task 1 are consumed by the exact same names in Task 2 (`active_provider.base_url`) and Task 3 (`resolved_chat_model`/`resolved_condenser_model`). `create_json_completion(client, model, messages, max_tokens, structured=None)` signature is identical across its definition (Task 2) and all three call sites (Task 3). Consistent. ✅
