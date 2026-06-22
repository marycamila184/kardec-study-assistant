# Funcionalidade #4 — Abrir o Evangelho

**Date:** 2026-06-22  
**Status:** Implemented  

## Overview

A lightweight mode for spontaneous reading from *O Evangelho segundo o Espiritismo*. The user opens it and receives one passage from the book — the original text, nothing more. No AI generation, no summaries. Below the passage, the client displays quick action buttons ("Estudar mais", "Gostaria de compreender") that connect to Funcionalidades #1 and #2.

The passage is the same for all users on a given calendar day, changing at midnight. It is selected deterministically from the date, so the result is stable across server restarts without any external cache or database.

---

## Section 1 — API and Response Shape

One new endpoint: `GET /evangelho`

No request body, no parameters.

**Response:**
```json
{
  "date": "2026-06-22",
  "content": "...",
  "source": {
    "book": "O Evangelho segundo o Espiritismo",
    "chapter_title": "Aos Espíritos e aos Médiuns",
    "item_number": "section-4",
    "subchunk_index": 1,
    "total_subchunks": 1
  }
}
```

**Field semantics:**
- `date` — ISO-format string of the server's current date (`datetime.date.today().isoformat()`). The client compares this against its stored date and discards its local cache if they differ.
- `content` — the passage text, verbatim from the ChromaDB document.
- `source.book` — always `"O Evangelho segundo o Espiritismo"`.
- `source.chapter_title`, `source.item_number`, `source.subchunk_index`, `source.total_subchunks` — from the chunk's metadata. Gives the client enough context to label the reading and wire quick action buttons (e.g., `/study` with `book` + `item_number`).

**Error case:** If ChromaDB returns no Evangelho chunks (index not yet built), return HTTP 503 with body `{"error": "evangelho_not_indexed"}`. Never return a 500.

---

## Section 2 — Selection Mechanism

All logic runs at request time — no background jobs, no scheduled tasks.

1. **Fetch:** `VectorStore.get_by_filter({"book": {"$eq": "O Evangelho segundo o Espiritismo"}})` — returns all Evangelho chunks.
2. **Sort:** sort chunks by their ChromaDB ID string for stable ordering independent of insertion sequence.
3. **Seed:** `random.seed(datetime.date.today().isoformat())` — ties the random state to the calendar day.
4. **Select:** `random.choice(chunks)` — deterministic for the day, changes automatically at midnight when the date string changes.

No LLM call. No AI generation. The endpoint is fast and cheap.

---

## Out of Scope (MVP)

- Per-user personalisation of the daily passage
- Timezone-aware midnight (UTC is sufficient for MVP)
- Curation of which chunks are eligible (all Evangelho chunks are fair game)
- Quick action buttons (client responsibility, API provides the metadata to construct them)
