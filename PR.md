# feat: complete MVP — RAG agents, 4 study modes, mobile UX

## Summary

This PR brings the full MVP from `development` into `main` — 85 commits across backend and frontend.

### Backend
- **4 RAG agents**: Explicador (`/study`), Reflexivo (`/reflect`), Curador (related-item annotation), Generator (`/chat`)
- **Retriever**: semantic search via ChromaDB + `BAAI/bge-m3` embeddings (800-char chunks); `book_filter` with automatic fallback to all books when no results found in the selected book
- **Daily passage** (`/evangelho`): deterministic daily item from curated `trecho_diario.md`; chapter summaries attached
- **Curated learning paths**: `GET /paths`, `GET /paths/{path_id}` served from static JSON
- **Safety guardrails**: no personification of "o Espiritismo", no unsolicited advice, medical/mediumship caveat keyword list in Reflexivo
- **LLM**: `llama-3.3-70b-versatile` via Groq; embeddings via `BAAI/bge-m3`

### Frontend
- **4 modes**: Tirar uma Dúvida, Estudar uma Obra (guided trilhas + free Explorar), Refletir sobre uma Situação, Trecho do Dia
- **Conversation persistence**: localStorage; load/delete/favorite; cached messages skip typewriter animation
- **Typewriter reveal**: word-by-word animation for all AI responses
- **Source citation chips** + **Related items modal** + **Reflection question buttons**
- **Suggested mode**: inline "Estudar este item completo" button when `/chat` detects an item lookup

### Mobile UX
- Bottom nav: 4 tabs with icons (Estudar, Dúvida, Refletir, Hoje)
- Sidebar drawer: slide-in animation, `min(300px, 85vw)` width, conversations-only on mobile
- InputBar: info-icon tooltip replacing hint text; shorter placeholders per mode
- Share: WhatsApp (`wa.me`) + download image; icon-only on mobile; restricted to Trecho do Dia and trilha completion

## Test coverage

```
179 passed, 1 warning in 11.33s
Overall coverage: 87% (945 statements, 124 missed)

Key modules:
  src/api/routes.py          100%
  src/api/schemas.py         100%
  src/rag/mode_detector.py   100%
  src/rag/reflect_prompt.py   96%
  src/rag/evangelho.py        96%
  src/rag/reflect.py          93%
  src/rag/retriever.py        91%
  src/rag/generator.py        75%  (LLM call paths need integration tests)
```

## Checklist
- [x] `uv run pytest` — 179 tests pass
- [x] `uv run black src/` — no formatting issues
- [x] `uv run isort src/` — imports sorted
- [x] Legacy test files removed (`test_study.py`, `test_study_prompt.py`)
- [ ] Run ingestion pipeline after deploy (`uv run python -m src.ingestion.pipeline`)
- [ ] Test all 4 modes end-to-end with real API key
- [ ] Test `book_filter` fallback note in Explorar Obras
- [ ] Test WhatsApp share from Trecho do Dia on mobile

🤖 Generated with [Claude Code](https://claude.com/claude-code)
