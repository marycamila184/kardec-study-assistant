# Funcionalidade #3 — Refletir sobre uma Situação

**Date:** 2026-06-22  
**Status:** Implemented  

## Overview

Mode for users who want to see a life situation through the lens of Kardec's doctrine and receive personal reflection prompts. The user describes what they are going through — grief, emptiness, a difficult relationship, a mediumistic experience, a joyful event — and the system returns what the doctrine says about it, how it connects to their situation, and three reflection questions for personal contemplation.

**This mode never gives advice.** It never suggests action, medication, lifestyle changes, or any course of behavior. It is a doctrinal mirror and reflection facilitator only.

---

## Section 1 — API and Response Shape

One new endpoint: `POST /reflect`

**Request:**
```json
{
  "situation": "meu pai faleceu e estou com medo e sentindo angústia",
  "conversation_history": []
}
```

**Response:**
```json
{
  "opening": "...",
  "doctrine_connection": "...",
  "reflection_questions": ["...", "...", "..."],
  "complementary_items": [
    { "book": "O Livro dos Espíritos", "item_number": "149", "preview": "..." }
  ],
  "sources": [
    { "book": "O Livro dos Espíritos", "chapter_title": "Da Morte", "item_number": "149" }
  ],
  "not_found": false,
  "generation_failed": false
}
```

**Field semantics:**
- `opening` — tone-adaptive first paragraph. Empathetic for pain, loss, fear, difficulty; warm and joyful for positive situations (birth, gratitude, celebration). Determined by the LLM reading the situation text.
- `doctrine_connection` — what the doctrine says about the situation + how it connects, grounded strictly in retrieved passages.
- `reflection_questions` — always exactly 3 questions for personal contemplation (journaling-style, not follow-up prompts for the app).
- `complementary_items` — up to 3 semantically related items from the retrieval results that were not used as primary sources. Each has `book`, `item_number`, `preview` (first 200 chars).
- `sources` — the primary retrieved chunks used to build `doctrine_connection`. Shape: `book`, `chapter_title`, `item_number`.
- `generation_failed` — true if the LLM call throws; `opening` and `doctrine_connection` are empty, `reflection_questions` is empty list. `sources` are still returned from the retrieval step.

`conversation_history` is client-owned (stateless API). Sent for context in follow-up turns within the same reflection session.

---

## Section 2 — Retrieval

Same semantic pipeline as the existing `/chat` endpoint:

1. Encode `situation` text → semantic search on ChromaDB → top 5 chunks filtered by `max_distance`
2. If no chunks returned → return `not_found: true` response without calling the LLM (same pattern as `/chat`)
3. **Primary sources:** first 2 chunks from the result list → used to build `doctrine_connection` and populate `sources`
4. **Complementary items:** next 3 chunks (indices 2–4) → populate `complementary_items` with `preview = content[:200]`

One retrieval call per request. No second query.

---

## Section 3 — Prompt and Guardrails

The system prompt has three layers, applied in order:

### Tone adaptation
The LLM reads the emotional weight of the `situation` field and calibrates the `opening` accordingly:
- Loss, grief, fear, pain, difficulty → empathetic, gentle opening
- Joy, celebration, positive milestones → warm, uplifting opening
- Neutral or ambiguous → compassionate but measured opening

No rule-based tone detection; the LLM determines tone from the situation text.

### Hard no-advice constraint (verbatim in system prompt)
```
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria",
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação,
doação, separação, mudança de comportamento, ou qualquer outro curso de ação.
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados.
```

### Medical/mediumship caveat (conditional)
Before the LLM call, a keyword check on `situation` detects potential clinical or mediumistic symptoms. Trigger keywords (case-insensitive):
`vozes`, `sombras`, `escuto`, `vejo entidades`, `ouço`, `pânico`, `desespero`, `não consigo dormir`, `alucinação`

When triggered, one sentence is appended to the system prompt:
```
Se a situação descrita puder ter causas clínicas, acrescente UMA frase curta
ao final indicando que o apoio de um profissional de saúde é também valioso —
sem substituir a visão espírita e sem fazer diagnósticos.
```

The caveat never replaces the doctrinal response; it is one sentence appended after the reflection questions.

### JSON output format
The LLM returns structured JSON with keys: `opening`, `doctrine_connection`, `reflection_questions` (list of 3 strings). `complementary_items` and `sources` are built from retrieval results by the server, not by the LLM.

---

## Section 4 — Mode Suggestion Detection

**No auto-detection from `/chat`.** The Refletir mode is always user-initiated from a dedicated button or tab in the UI. No `suggested_mode` value is added to `/chat` responses for this mode.

Rationale: personal situations do not have reliable regex signals — phrases like "estou passando por" or "me sinto" also appear in doctrinal questions. False positives (offering reflection mode to someone asking a doctrinal question) would be disruptive. Explicit user selection eliminates this risk entirely.

---

## Out of Scope (MVP)

- Curated reflection paths (noted as future enhancement)
- Multi-turn stateful reflection sessions (client sends `conversation_history` but the server does not store it)
- Auto-detection of reflection intent from `/chat`
- External Spiritist authors or readings beyond Kardec's 5 books
