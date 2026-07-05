# Batch A — Backend Quality Fixes (Design)

**Date:** 2026-07-05
**Status:** Approved, pending implementation plan
**Scope:** First of two sub-projects improving conversation flow. Batch A covers
low-risk backend correctness/quality fixes plus one small additive frontend
button. Batch B (frontend conversation architecture: unified stores, streaming,
cross-mode UX) is a separate spec.

## Goal

Improve retrieval quality and observability in the RAG pipelines, and make the
mode system feel connected by routing situational `/chat` questions toward
Refletir — without touching the large frontend conversation architecture.

## The four fixes

### A1. Condense query for `/reflect` multi-turn retrieval

**Problem:** `reflect.py` retrieves on the raw `situation` string
(`reflect.py:26`). In a multi-turn reflection, `situation` is the latest turn
(e.g. a clicked reflection question or a short follow-up), so retrieval loses
the original situation and degrades. `/chat` already solves this with
`condense_query` (`generator.py:20`), but that helper is private to the
generator module.

**Change:**
- Extract `condense_query` into a new shared module
  `src/rag/query_condenser.py`. `generator.py` imports it from there (behavior
  unchanged for `/chat`).
- In `reflect.py`, when `conversation_history` is non-empty, condense
  `situation` + history into a standalone search query before `retrieve()`.
  First-turn reflections (empty history) skip condensation — behavior unchanged.
- Resilience: on any condense failure, fall back to the raw `situation` (same
  pattern `generator.py` already uses).

**Interface:** `condense_query(question: str, history: list[dict]) -> str`.
The reflect caller passes `situation` as `question` and its
`conversation_history` as `history`.

### A2. Tighten Explicador related-items query

**Problem:** `explicador.py:25` retrieves related items using the full
concatenated `original_text` (potentially several subchunks) as the embedding
query. Long queries dilute retrieval precision.

**Change:** query on the **first subchunk only** (`chunks[0]["content"]`).
`original_text` still feeds the Explicador prompt and the Curador call
unchanged — only the semantic search query narrows.

**Constraint honored:** retrieval still happens before the LLM calls, so the
existing parallel `ThreadPoolExecutor` structure (Explicador + Curador) is
preserved. No added latency. (Using `conceitos_chave` as the query was
rejected because it would serialize the pipeline behind the Explicador call.)

### A3. Failure-path logging

**Problem:** the pipelines swallow `except Exception` into `generation_failed`
/ fallback returns with no logging (`generator.py`, `reflect.py`,
`explicador.py`, `curador.py`). Production failures are invisible.

**Change:** add a module-level `logging.getLogger(__name__)` to each of the
four modules and log at each currently-silent failure/fallback point:
- `generator.py`: retrieve failure, generation failure, book-fallback taken,
  not_found.
- `reflect.py`: retrieve failure, reflexivo parse/call failure, not_found.
- `explicador.py`: related-items retrieve failure, explicador call failure.
- `curador.py`: curador call/parse failure (fallback to raw candidates).

Use `logger.exception(...)` inside `except` blocks (captures traceback) and
`logger.warning(...)` for non-exception fallbacks (e.g. not_found). No behavior
change — pure observability. No logging configuration is added here (the app /
uvicorn owns handler config); modules only emit.

### A4. Bidirectional mode detection (+ small frontend button)

**Problem:** `detect_suggested_mode` (`mode_detector.py`) only nudges
`/chat -> estudar_obra`. A situational/emotional `/chat` question
(e.g. "tenho medo de morrer") gets a dry factual answer with no path toward the
Refletir experience built for exactly that.

**Backend change:**
- Add a situational keyword/pattern set to `mode_detector.py` (e.g. *medo,
  luto, ansiedade, sozinho, perdi, sofrimento, angústia, culpa, raiva,
  desespero, não sei lidar, …*).
- `detect_suggested_mode` returns `"refletir"` when the question reads as
  situational. **Tie-break:** the existing `estudar_obra` detection wins when
  both match (specific item-lookup intent beats a general emotional cue).
- No schema change: `ChatResponse.suggested_mode` already carries a string.

**Frontend change (the one UI touch in Batch A):**
- Mirror the existing `estudar_obra` button (`App.jsx:806-820`). When
  `msg.suggestedMode === 'refletir'`, render a single terracotta-outline button
  `🪞 Refletir sobre esta situação` below the answer.
- On click: `switchMode('refletir')`, then seed the flow with the user's
  original question as the situation (call the same path
  `handleReflectSubmit` uses so the Refletir thread opens with the
  tone-adaptive response). The original question text is available on the
  preceding user message in `msgs`.
- Accent color `#C8856A` (Refletir's `BRAND_TERRACOTTA`), matching the
  `isReflection` badge, vs. the blue used for the Estudar button.

**Note on `switchMode`:** `switchMode` currently clears `msgs`
(`App.jsx:149`). Seeding must therefore capture the question text *before*
switching, then submit it into the fresh Refletir thread. (The broader
context-preserving cross-mode refactor is Batch B; here we only need the seed
to survive the switch.)

**Mode-timing hazard:** `sendText` captures `requestMode = mode` from the
closure at call time (`App.jsx:165`), and `switchMode`'s `setMode('refletir')`
is an async state update. If the handler calls the reflect submit synchronously
right after `switchMode`, `mode` may still be the stale value and the request
would route to `/chat`. The existing `redirectToDuvida` handles this with a
`setTimeout(..., 50)` (`App.jsx:524`). The plan must use an equivalent
guarantee — defer the submit until after the mode state has flushed, or call
`reflectSituation` directly rather than routing through `sendText`'s
mode-branch. This is called out here so it is not rediscovered during
implementation.

## Testing

- `query_condenser`: with history (condenses), without history (skips),
  condense raises -> falls back to raw input. Reflect integration: multi-turn
  path calls condenser; first turn does not.
- `mode_detector`: refletir cases, estudar-wins-tie, neither -> None, existing
  estudar cases still pass.
- `explicador`: assert the related-items retrieve is called with the first
  subchunk, not the full `original_text`.
- Logging: `caplog` asserts a record is emitted on each failure/fallback path.
- Frontend button: unit/interaction test that a `refletir` suggested_mode
  renders the button and clicking it enters Refletir mode seeded with the
  question. (Follow existing frontend test conventions if present; otherwise a
  lightweight render/click test.)

## Out of scope (Batch B)

Unifying the three conversation stores, consistent history across all entry
points, real SSE streaming, and the context-preserving cross-mode transitions.
Batch A deliberately leaves `switchMode`'s clear-on-switch behavior in place.
