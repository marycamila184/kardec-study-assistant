# Env-switchable LLM provider + structured JSON output

**Date:** 2026-07-20
**Status:** Approved (design)

## Problem

The backend talks to a single hardcoded LLM endpoint (Groq, OpenAI-compatible)
via `src/rag/llm_client.py`. Two pain points:

1. **Rate limits.** The Groq free tier caps ~12k TPM. Full probe runs
   (`scripts/probe_backend.py`) hit `generation_failed` mid-thread — the last
   run's G4/G6 WARNs were rate-limit timeouts, not app bugs. The Anthropic API
   is a non-starter on cost, and the user wants to try open models.
2. **Fragile structure.** No call uses `response_format`. All structure — the
   reflect JSON, the `sensitivity`/`orchestrator` classifiers, and `/chat`'s
   `[FONTES]`/`[SEGUIR]` trailer markers — is coerced by prompt + regex
   extraction (`json_extract.py`, `sensitivity._JSON_RE`,
   `reflect_prompt._extract_json_object`). Weaker/cheaper open models drop or
   malform this more often (see the C4 caveat gap surfaced by the probe run).

## Goal

Let the operator switch LLM provider with one env var — **Groq**, **OpenRouter**,
or **Together AI** — reusing the existing OpenAI-compatible client, and add
schema-enforced JSON output to the JSON-producing calls where the provider
supports it, without regressing behavior on providers that don't.

## Non-goals (YAGNI)

- No full per-endpoint `json_schema` — JSON-object mode plus the existing regex
  extraction is enough and far more portable across providers/models.
- No change to `/chat`'s `[FONTES]`/`[SEGUIR]` trailer-marker contract, its
  `_strip_trailing_markers` logic, or its probes.
- No local-inference (Ollama) path in this change — considered and set aside;
  the 8GB-GPU ceiling is a 7B, below the current 70B.
- No streaming, retry-budget, or concurrency changes.

## Design

### 1. Provider registry

A static table in `src/core/config.py` mapping a provider key to its connection
details and default model names:

| provider | base_url | api key env | default `chat_model` | default `condenser_model` |
|---|---|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | `llama-3.1-8b-instant` |
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | `deepseek/deepseek-chat` | `meta-llama/llama-3.1-8b-instruct` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | `deepseek-ai/DeepSeek-V3` | `meta-llama/Llama-3.1-8B-Instruct-Turbo` |

Represented as a frozen dict of small dataclass/namedtuple records
(`base_url`, `api_key_field`, `default_chat_model`, `default_condenser_model`).

### 2. Config resolution (`src/core/config.py`)

New / changed `Settings` fields:

- `llm_provider: str = "groq"` — selects the registry row. **Default `groq`
  keeps every existing `.env` working unchanged.**
- `openrouter_api_key: str | None = None`, `together_api_key: str | None = None`
  — optional, alongside the existing `groq_api_key`.
- `chat_model` / `condenser_model` become **optional overrides**:
  `str | None = None`. When unset, resolve to the selected provider's default.

Resolution helpers (properties):

- `active_provider` → the registry record for `llm_provider`; raises a clear
  `ValueError` if `llm_provider` is not a known key.
- `active_api_key` → the key for the selected provider; raises a clear
  `ValueError` naming the missing env var if it's unset/empty.
- `resolved_chat_model` → `chat_model` if set, else provider default.
- `resolved_condenser_model` → `condenser_model` if set, else provider default.

Precedence: explicit `CHAT_MODEL` / `CONDENSER_MODEL` env override > provider
default. So switching provider is one env var; pinning a specific model is one
more.

### 3. Client construction (`src/rag/llm_client.py`)

`get_client()` keeps its signature (callers are unchanged). Internally it reads
`settings.active_provider` + `settings.active_api_key` and builds
`OpenAI(base_url=..., api_key=...)`. The module-level singleton is preserved.

Call sites already pass the model explicitly; they switch from
`settings.chat_model` / `settings.condenser_model` to
`settings.resolved_chat_model` / `settings.resolved_condenser_model`.

Affected call sites (model reference only):
`explicador.py`, `reflect.py`, `curador.py`, `generator.py`,
`generate_chapter_summaries.py` (chat model); `sensitivity.py`,
`orchestrator.py`, `query_condenser.py` (condenser model).

### 4. Structured JSON helper (`src/rag/llm_client.py`)

New thin helper:

```
create_json_completion(model, messages, max_tokens, temperature=None) -> completion
```

- Attempts `chat.completions.create(..., response_format={"type": "json_object"})`.
- On a provider/model rejection of the param (`openai.BadRequestError`, or any
  4xx indicating `response_format` unsupported), it **retries once without**
  `response_format` and returns that. This is the graceful-degradation path so
  the same code works across providers/models with differing support.
- Returns the raw completion object; **callers keep their existing regex
  extraction** as the parse layer. Schema-clean output is a bonus, never a new
  hard dependency.

A module-level flag derived from config (`settings.structured_output: bool =
True`) lets the operator disable the `response_format` attempt entirely for a
model known not to support it, skipping the failed first call.

The three JSON call sites route their `create(...)` through this helper:

- `src/rag/sensitivity.py` — `classify_sensitivity` (`{"nivel": ...}`)
- `src/rag/orchestrator.py` — `classify_intent`
- `src/rag/reflect.py` — the structured reflect object

`query_condenser.py` returns a plain condensed string, not JSON — **not**
routed through the helper. `/chat`'s generator uses trailer markers, not JSON —
**not** routed through the helper.

Note: JSON-object mode on some providers requires the token "json" to appear in
the prompt. The three affected system prompts already instruct JSON output and
contain the word; verify during implementation and add it if missing.

### 5. Error handling

- Unknown `llm_provider` → `ValueError` at settings access, message lists valid
  keys.
- Missing API key for the selected provider → `ValueError` naming the expected
  env var.
- `response_format` rejected by provider/model → automatic retry without it
  (§4); no operator action needed.
- All existing per-call `try/except` (which default classifiers to safe values
  on any failure) is preserved.

## Testing

Unit (pytest, no network):

- Provider resolution: `llm_provider` → correct `base_url` / default models.
- Override precedence: explicit `chat_model` / `condenser_model` beats provider
  default; unset falls back to provider default.
- Missing-key and unknown-provider raise clear `ValueError`s.
- `create_json_completion` fallback: mock the client so the first call raises
  `BadRequestError` and assert the second call is made **without**
  `response_format`, and that a supported provider passes `response_format`
  through unchanged.
- Full existing suite (373 tests) stays green.

Acceptance (live, manual):

- `LLM_PROVIDER=openrouter` and `LLM_PROVIDER=together` each: run
  `scripts/probe_backend.py` against a live server. No rate-limit interference
  → a complete Group G run. The 40 probe checks are the cross-provider
  scorecard; compare against the current Groq baseline (40 PASS / C4 WARN).

## Rollout

Backward-compatible: absent any new env vars, `llm_provider` defaults to `groq`
and behavior is identical to today. Switching is `LLM_PROVIDER=openrouter` (or
`together`) plus the matching API key in `.env`.
