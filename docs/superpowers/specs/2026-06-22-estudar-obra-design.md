# Funcionalidade #1 — Estudar uma Obra

**Date:** 2026-06-22  
**Status:** Implemented  

## Overview

Mode for studying a specific item, chapter, or theme from Kardec's works. Returns the original text, a modern-language explanation, a practical example, and related references. Users access content either by item number (Q.132, item 42) or through curated learning paths.

---

## Section 1 — Learning Paths Data Model

Paths are curated JSON files stored in `data/paths/`. Each file is one path; the AI generates drafts and the maintainer reviews them before committing.

**File naming:** `data/paths/<path-id>.json`  
**Discovery:** server reads all `.json` files in that directory at startup (or on each request — no hot-reload needed for MVP).

**Schema:**

```json
{
  "id": "fundamentos-da-doutrina",
  "title": "Fundamentos da Doutrina Espírita",
  "description": "Para quem está começando. Apresenta os pilares do espiritismo em ordem natural.",
  "level": "iniciante",
  "steps": [
    {
      "book": "O Livro dos Espíritos",
      "item_number": "1",
      "label": "O que é Deus?"
    },
    {
      "book": "O Livro dos Espíritos",
      "item_number": "76",
      "label": "Existem espíritos maus?"
    }
  ]
}
```

`level` is a free-form string (`"iniciante"`, `"intermediário"`, `"avançado"`) displayed in the UI — no logic depends on it.

**Progress tracking:** client-side. The API returns the full path; the client records which steps the user completed and sends the current `item_number` with each `/study` request.

---

## Section 2 — API Endpoints

Three new endpoints alongside the existing `/chat`:

### `GET /paths`

Returns index of all available paths (no steps — just enough to list them).

```json
[
  {
    "id": "fundamentos-da-doutrina",
    "title": "Fundamentos da Doutrina Espírita",
    "description": "...",
    "level": "iniciante",
    "step_count": 12
  }
]
```

### `GET /paths/{path_id}`

Returns full path with all steps. 404 if `path_id` not found.

```json
{
  "id": "fundamentos-da-doutrina",
  "title": "...",
  "description": "...",
  "level": "iniciante",
  "steps": [ ... ]
}
```

### `POST /study`

Main endpoint for Funcionalidade #1. Accepts a specific item reference and returns structured study content.

**Request:**

```json
{
  "book": "O Livro dos Espíritos",
  "item_number": "132",
  "conversation_history": []
}
```

**Response:**

```json
{
  "original_text": "...",
  "explanation": "...",
  "practical_example": "...",
  "related_items": [
    { "book": "O Livro dos Espíritos", "item_number": "133", "preview": "..." }
  ],
  "sources": [
    { "book": "O Livro dos Espíritos", "item_number": "132", "chapter_title": "..." }
  ],
  "generation_failed": false
}
```

`conversation_history` is owned by the client (stateless API). The client sends it so follow-up questions within a study session preserve context.

---

## Section 3 — Content Generation

**Pipeline for `POST /study`:**

1. **Direct lookup:** query ChromaDB with `item_number` + `book` filter. Fetches the exact chunk(s) — these become `original_text`.
2. **Related items:** semantic search using the item content as query, filtering out the same `item_number`, top 3 by distance. These populate `related_items`.
3. **Single LLM call** with educator prompt (see below).

**System prompt constraints:**
- Never elaborate doctrine beyond the retrieved excerpts
- If the chunk is very short and content is insufficient, say so explicitly rather than improvising
- Clearly separate original text from the AI's explanation

**Educator prompt structure:**

```
Você é um educador especializado na obra de Allan Kardec. 
Baseando-se SOMENTE nos trechos abaixo, responda em três partes:
1. Explique em linguagem moderna e acessível
2. Dê um exemplo prático da vida cotidiana
3. Indique como este trecho se conecta com os demais fornecidos

Trechos recuperados:
{chunks}

Nunca elabore doutrina além do que está nos trechos. Se o trecho for muito breve 
para uma explicação completa, diga isso explicitamente.
```

---

## Section 4 — Mode Suggestion Detection

The existing `POST /chat` endpoint gains a `suggested_mode` field in its response. When the server detects that the user's query looks like a study request, it suggests switching to Funcionalidade #1.

Detection is regex-based (no extra LLM cost):

```python
STUDY_PATTERNS = [
    r'\bquestão\s+\d+',
    r'\bitem\s+\d+',
    r'\bq\.\s*\d+',
    r'explique\s+a\s+questão',
    r'o que\s+(diz|fala)\s+.+\d+',
]
```

If any pattern matches, `suggested_mode` is `"estudar_obra"`. The client shows a prompt (e.g., a chip/button) inviting the user to switch. The user must explicitly trigger the switch — it is never automatic.

**Error handling:**

| Condition | Behavior |
|---|---|
| `item_number` not found in ChromaDB | 404 with `{"error": "item_not_found", "item_number": "..."}` |
| `path_id` not found | 404 with `{"error": "path_not_found", "path_id": "..."}` |
| LLM call fails | Return `original_text` from ChromaDB with `generation_failed: true`; explanation/example fields empty |
| Chunk too short for full response | LLM instructed to say so explicitly; no hallucinated doctrine |

---

## Section 5 — Sensitive and Controversial Topics

Kardec's doctrine addresses many morally sensitive topics directly (abortion, racial equality, moral suffering from violence). Blocking these queries would prevent users from finding what the doctrine actually says — contrary to the tool's purpose.

**Three-case treatment:**

**Case 1 — Doctrine has clear text:** Answer normally. The original passage leads the response; the AI explains it. Source attribution is always visible.

**Case 2 — Doctrine touches it indirectly:** Retrieve the closest relevant passages, explain what the doctrine says, and prefix the explanation with a brief framing: *"O Espiritismo aborda este tema pela perspectiva de [X]. Segue o que Kardec escreveu:"*

**Case 3 — No doctrine grounding exists:** Return the same "not found" response as any other ungrounded query. No improvised answer.

**Hard constraint in every prompt:**  
> *"Nunca elabore doutrina além dos trechos recuperados. Se o tema não estiver nos livros, diga que não encontrou."*

No topic blocklist. The doctrine's own moral positions are the boundary, not a keyword filter.

---

## Out of Scope (MVP)

- Ações Rápidas (cross-cutting feature, separate design)
- Path authoring UI (maintainer edits JSON files directly)
- Server-side progress tracking
- Hot-reload of path files
