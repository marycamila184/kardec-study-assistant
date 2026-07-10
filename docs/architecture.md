# Architecture — deep reference

Detailed implementation notes for the Kardec Study Assistant. `CLAUDE.md` holds the orientation and the behavior rules; this file holds the "how each layer actually works" detail. Read the relevant section when you touch that layer.

## Parsing Layer (`src/parsing/`)

Pipeline:

1. `cleaner.py` — strips LlamaCloud artifacts: page-number headers (`# 13`), `---` separators, hyphenated line breaks.
2. `parser.py` — parses cleaned Markdown into structured chunks. Fields: `book`, `part`, `chapter`, `chapter_title`, `subsection`, `item_number`, `subchunk_index`, `total_subchunks`, `content`, plus:
   - `footnotes` — list of `{"number", "content"}`; **only** the footnotes whose `___…___` block appears immediately after this specific paragraph. Per-paragraph, not per-section.
   - `title_footnotes` — footnotes whose block appears immediately after the heading (`chapter_title`/`subsection`) this chunk lives under. Carried identically on every chunk under that heading; reset at the next heading.

   **Footnote Markdown format:** `(N) footnote text`, wrapped in an opening and closing separator line of 3+ underscores:
   ```
   Paragraph referencing (1).
   __________
   (1) Footnote text.
   __________
   Next paragraph.
   ```
   The separator pair acts as open/close delimiters. If the opening separator appears right after a heading with no content yet → title footnote; otherwise it belongs to the preceding content paragraph.

3. `chunking.py` — splits long segment content into ≤800-char subchunks at line boundaries (each Markdown line is a complete paragraph, so splits never cut mid-paragraph). **800 is the ceiling**, calibrated to typical item length across the 4 books (median 440–1600 chars, p90 ~6600), not the model's technical limit (`bge-m3` supports 8192 tokens) — larger chunks dilute retrieval precision.
4. `parsing_pipeline.py` — orchestrates all books; maps filenames to canonical names via `BOOK_NAME_MAP`. `trecho_diario.md` is intentionally absent and silently skipped (consumed separately by `evangelho.py`).

**Numbered items** (`123. text`) are the primary structural unit:
- **Livro dos Espíritos, Livro dos Médiuns** — single global sequence (1..N).
- **Evangelho, Céu e Inferno** — per-chapter sequences (reset to 1 at each chapter heading).

Markdown source files (`data/markdown_files/`) are hand-reviewed and authoritative — do not regenerate from PDFs.

## Ingestion Layer (`src/ingestion/`)

Run once (or re-run to rebuild).

- `embeddings.py` — wraps `SentenceTransformer` (`BAAI/bge-m3`); module-level singleton. Calls `huggingface_hub.login()` on startup if `HF_TOKEN` is set.
- `vectorstore.py` — wraps ChromaDB: `upsert`, `query` (semantic), `get_by_filter` (metadata-only).
- `pipeline.py` — JSON → batches of 64 → embed → upsert. `_build_document` appends footnotes after content, capped at 3000 chars total so the embedding model is never truncated; full footnote text stays in JSON metadata.

Document ID: `{book_filename_stem}_{item_number}_{subchunk_index}` — stable across re-runs (upsert idempotent).

## RAG Layer (`src/rag/`)

Each mode has a dedicated prompt file + pipeline file.

**Shared infrastructure:**
- `retriever.py` — `retrieve(query, top_k)`: semantic search filtered by cosine-distance threshold. `retrieve_by_item(book, item_number)`: metadata-only lookup returning all subchunks of an item. Both strip the ingestion-baked `\n[Nota N] …` footnote suffix off `content`, exposing it separately as `footnote_context` (`""` if none).
- `mode_detector.py` — `detect_suggested_mode(question)`: regex intent → `"estudar_obra"` / `"refletir"` / `None` (estudar_obra wins on tie). `extract_study_reference(question)`: `{"item_number", "book"}` by regex; "questão N"/"Q. N" default book to O Livro dos Espíritos, "item N" leaves `null`. Accent-tolerant; detection and extraction patterns must stay in sync. `is_smalltalk(text)`: pure-acknowledgment detector for the `/chat` short-circuit. (Superseded for suggested-mode by the orchestrator, but kept + unit-tested.)
- `query_condenser.py` — `condense_query(question, history)`: rewrites a follow-up + history into a standalone Portuguese search query (`condenser_model`) before embedding; forbids replacing doctrine terms with generic synonyms. Used by `/chat` and multi-turn `/reflect`; callers log and fall back to raw text on failure.
- `orchestrator.py` — `classify_intent(message, current_mode, history)`: small-LLM classifier returning `{"mode": tirar_duvida|refletir|estudar_obra|None, "confidence": high|low}`. Deterministic safety (`needs_crisis_note`, `is_smalltalk`) runs before any LLM call; nudge only on `high` confidence, never toward `current_mode`; any failure → `{"mode": None}`. History is prefixed into the prompt for follow-up context. Wired into `/chat` and `/reflect` via `_answer_with_nudge` (runs concurrently with generation, capped by `_CLASSIFY_TIMEOUT_S`).

**Footnote handling:** footnotes are baked into stored `content` at ingestion (embedding only); `retriever.py` strips them on every read so they never leak into text, prompts, or citations — exposed as `footnote_context` for callers that want them as grounding (currently only Explicador).

**Explicador** (`/study`) — `explicador_prompt.py` + `explicador.py`:
- Socratic tutor. Output JSON `{"contexto", "conceitos_chave": [...]}`. `perguntas` was removed from the prompt (frontend never showed it) but `parse_explicador_json` still tolerates it (`[]` when absent) and the API field remains. `contexto` (3–6 sentences) places the item in the doctrine and may add well-known historical/cultural background from general knowledge — but doctrine stays grounded in the retrieved text and the prose must make the distinction legible. `conceitos_chave` may include a short clarifying gloss. Forbidden: summarizing/paraphrasing the passage; personifying "o Espiritismo". `parse_explicador_json` → `(contexto, conceitos_chave, perguntas)`.
- Pipeline: `retrieve_by_item` → semantic related items → Explicador LLM (fed the main passage's `footnote_context`) → `curar()`. Returns `original_text`, `contexto`, `conceitos_chave`, `perguntas`, `related_items`, `sources`, `generation_failed`.

**Curador** (called by Explicador + Reflexivo) — `curador_prompt.py` + `curador.py`:
- Given the main passage + up to 3 candidates, selects 1–3 doctrinally connected ones and writes one Portuguese sentence per connection. Output JSON `[{"index", "conexao"}]`. `curar(main_text, candidates)` merges `conexao` and `chapter` into candidate metadata; on any failure falls back to raw candidates without `conexao` (never breaks the caller). `chapter` is required so the frontend can disambiguate per-chapter numbering (Evangelho, Céu e Inferno).

**Reflexivo** (`/reflect`) — `reflect_prompt.py` + `reflect.py`:
- Tone-adaptive system prompt with a hard no-advice constraint. `CLINICAL_KEYWORDS` triggers an optional medical/mediumship caveat. `CRISIS_KEYWORDS` drives `needs_crisis_note()`; the fixed `CRISIS_NOTE` (CVV 188 / SAMU 192) is appended deterministically in code, never by the LLM. `build_reflect_messages(..., force_closing=True)` injects an "ENCERRAMENTO OBRIGATÓRIO" directive. Output JSON `{"opening", "doctrine_connection", "reflection_questions": [...], "is_closing"}` — 1–3 questions per turn. `parse_reflect_json` extracts the four fields.
- Pipeline: query condensation for multi-turn threads → semantic retrieval (top 5) → primary `[:2]` to the LLM → complementary `[2:5]` to `curar()`. After `CAP_ROUNDS` (5) rounds, `force_closing` is passed into the prompt and enforced post-hoc. Crisis detection runs on situation + full history; `CRISIS_NOTE` appended on every return path incl. `not_found`/failures. `not_found` keeps the warm tone. Returns `opening`, `doctrine_connection`, `reflection_questions`, `is_closing`, `complementary_items`, `sources`, `not_found`, `generation_failed`.

**Generator** (`/chat`) — `prompt.py` + `generator.py`:
- Rules: answer strictly from retrieved passages; separate source from AI; never close with unsolicited advice; never personify "o Espiritismo"; never end the answer with a question. Two machine-readable trailer lines: `[FONTES: 1, 3]` (passages used; `[FONTES:]` = none) and `[SEGUIR: q1 | q2]` (two follow-up questions answerable from the works, never repeating an already-asked question).
- Pipeline: optional condensation → retrieval → prompt → Groq. When the question references a specific item and the book is known (named or via `book_filter`), the item's chunks are fetched with `retrieve_by_item` and placed first (semantic dupes dropped); this also rescues the answer when semantic retrieval is empty/fails. `is_smalltalk` short-circuits pure acknowledgments before retrieval. Returns `answer`, `sources` (each with `book`, `chapter`, `item_number`, `excerpt`), `not_found`. Crisis handling as in `/reflect`. `_strip_trailing_markers` strips `[FONTES]`/`[SEGUIR]` (either order, tolerant of malformed variants): FONTES filters `sources` (no marker/only-invalid → all chunks; explicitly empty → none); SEGUIR → `suggested_questions` (max 2). Suggestions suppressed on crisis, `not_found`, generation failure.

**Daily passage** (`evangelho.py`): from `data/markdown_files/trecho_diario.md` — a curated 27-chapter subset of O Evangelho, kept out of the main ChromaDB collection so it never pollutes semantic search. Parsed once with `parse_md_to_json`, cached in memory (`_get_chunks()`). `get_daily_passage()` seeds `random` with today's ISO date, picks a chapter then an item, joins all that item's subchunks. No LLM.

## API Layer (`src/api/`)

Stateless. Clients own conversation history; `/chat` and `/reflect` accept it but the server stores nothing.

**`suggested_mode`** (on `/chat` and `/reflect`): a hint for the client to surface a cross-mode nudge button, produced by `orchestrator.classify_intent`. For `estudar_obra` the response also carries `suggested_item_number` / `suggested_book` (from `extract_study_reference`; book `null` unless named) so the client opens `/study` pre-filled. Both `null` for `refletir`/`None`. The client sends `current_mode` so the orchestrator never nudges toward the current mode.

**`Source` / `StudySource`** (`/chat` + `/reflect` `sources`):
```json
{ "book": "...", "chapter": "...", "chapter_ref": "...", "item_number": "...", "excerpt": "..." }
```
`excerpt` is the retrieved chunk text (footnote-stripped), used by the frontend citation-chip modal. `chapter` is the display title; `chapter_ref` is the machine chapter id (`"CAPÍTULO II"`) that `/study`'s `retrieve_by_item` filters on. `null` for legacy/unpopulated cases.

**`RelatedItem`** (`/study` `related_items` + `/reflect` `complementary_items`):
```json
{ "book": "...", "chapter": "...", "item_number": "...", "preview": "...", "conexao": "..." }
```
`conexao` is the Curador's one-sentence connection (`null` on Curador failure). `chapter` disambiguates per-chapter numbering.

## Curated Learning Paths (`data/paths/`)

One JSON per path, served statically (no DB; client owns progress). Schema: `id`, `title`, `description`, `level` (`curioso`/`estudante`/`aprofundado`), `steps[]` (each: `book`, `item_number`, `label`).

## Notes

- **Legacy:** `study.py` / `study_prompt.py` were the original `/study` implementation, superseded by `explicador.py`. Safe to delete.
- **Ações Rápidas** (client-side quick follow-up buttons) are wired but currently disabled everywhere (`showQuickActions={false}`) pending a UX redesign. Source citations (the clickable `📖` chips → `SourceModal`) are independent and always shown.
- The planned **Pesquisador** agent (query expansion before embedding) is not implemented.
