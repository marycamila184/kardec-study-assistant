# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kardec Study Assistant** is the backend of *Dialogando com a Doutrina* — a study companion for Allan Kardec's Spiritist works that uses RAG (Retrieval-Augmented Generation) to deliver grounded, accessible, and transparent answers. The goal is not to replace reading the works, but to lower the barrier for people with limited time or difficulty with the original language.

Responses must always be strictly retrieval-grounded (hallucinated doctrine is unacceptable) and must clearly separate what comes from the source text versus what comes from the AI.

### MVP Functionalities

All four modes are implemented.

| # | Mode | Endpoint | What it returns |
|---|---|---|---|
| 1 | **Estudar uma Obra** ✅ | `POST /study` | Original text + doctrinal context + key concepts (literal definitions from text) + Socratic reflection questions + curated related references with connection phrase |
| 2 | **Tirar uma Dúvida** ✅ | `POST /chat` | Grounded answer + excerpts used + sources + suggested mode |
| 3 | **Refletir sobre uma Situação** ✅ | `POST /reflect` | Tone-adaptive opening + doctrinal connection + 3 reflection questions + curated complementary readings with connection phrase |
| 4 | **Abrir o Evangelho** ✅ | `GET /evangelho` | Daily passage from O Evangelho (deterministic, no LLM) |

Supporting endpoints: `GET /paths`, `GET /paths/{path_id}` (curated learning paths), `GET /health`.

**Ações Rápidas** (quick follow-up actions) are client-side buttons rendered after each AI response (currently disabled everywhere — `showQuickActions={false}` — pending a UX redesign; the wiring below is intact and ready to re-enable):
- 📄 **Ler original** — displays the `obra.quote` block without a new LLM call
- 💡 **Explicar simples** — sends the passage snippet to `/chat` asking for a simpler explanation
- 🪞 **Reflexão** — calls `/reflect` with the passage snippet as situation
- 📚 **Relacionados** — opens `RelatedItemsModal` listing `relatedItems` (each with its `conexao` phrase); clicking an item calls `/study` for that item and appends the result as a new message

**Source citations** (independent of Ações Rápidas, always shown): `/chat` and `/reflect` responses render one clickable chip per source (`📖 book, Q.N`) below the answer text. Clicking a chip opens `SourceModal` showing that source's `excerpt` (the retrieved chunk text) and its reference.

### Agent Architecture

The RAG layer uses specialized agents per mode. Each agent has a dedicated prompt file and a pipeline file:

| Agent | Files | Mode | Calls |
|---|---|---|---|
| **Explicador** | `explicador_prompt.py`, `explicador.py` | `/study` | 1 LLM call (Socratic analysis) + 1 Curador call |
| **Reflexivo** | `reflect_prompt.py`, `reflect.py` | `/reflect` | 1 LLM call (tone-adaptive) + 1 Curador call |
| **Curador** | `curador_prompt.py`, `curador.py` | called by Explicador + Reflexivo | 1 LLM call (selects + annotates related items) |
| **Generator** | `prompt.py`, `generator.py` | `/chat` | optional condensation call + 1 LLM call |

The planned **Pesquisador** agent (query expansion before embedding) is not yet implemented.

> **Legacy files:** `study.py` and `study_prompt.py` were the original `/study` implementation and are superseded by `explicador.py`. They can be safely deleted.

## Environment

- Package manager: **uv** (`uv sync --group dev` to set up)
- Python 3.12+
- Requires a `.env` file with `GROQ_API_KEY` (Groq API key — OpenAI-compatible endpoint)

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run the parsing pipeline (MD → JSON)
uv run python -m src.parsing.parsing_pipeline

# Run the ingestion pipeline (JSON → ChromaDB)
uv run python -m src.ingestion.pipeline

# Start the API server (development)
uv run fastapi dev src/api/main.py

# Format and lint
uv run black src/
uv run isort src/

# Run tests
uv run pytest
uv run pytest tests/path/to/test_file.py::TestClass::test_name  # single test
```

## Architecture

The system is a multi-stage pipeline. Data flows in one direction:

```
PDFs → (LlamaCloud) → data/markdown_files/*.md
                              ↓
                    src/parsing/  (clean + parse)
                              ↓
                    data/json_files/*.json
                              ↓
                    src/ingestion/  (embed + index)
                              ↓
                    data/embeddings/  (vector store, gitignored)
                              ↓
                    src/rag/  (retrieve + prompt + generate)
                              ↓
                    src/api/  (FastAPI endpoints)
```

### Parsing Layer (`src/parsing/`)

Fully implemented. The pipeline is:

1. `cleaner.py` — strips LlamaCloud artifacts: page-number headers (`# 13`), `---` separators, hyphenated line breaks
2. `parser.py` — parses cleaned Markdown into structured chunks. Each chunk has these fields:
   - `book`, `part`, `chapter`, `chapter_title`, `subsection`, `item_number`, `subchunk_index`, `total_subchunks`, `content`
   - `footnotes` — list of `{"number": str, "content": str}`; contains **only** the footnotes whose `___…___` block appears immediately after this specific paragraph. Footnotes are per-paragraph, not per-section.
   - `title_footnotes` — list of `{"number": str, "content": str}`; footnotes whose `___…___` block appears immediately after the heading (`chapter_title` or `subsection`) under which this chunk lives. Carried identically on every chunk under that heading; reset when the next heading appears.

   **Footnote format in Markdown:** `(N) footnote text`, wrapped in an opening and a closing separator line of 3 or more underscores (`___`, `______`, etc. — all match):
   ```
   Paragraph referencing (1).
   __________
   (1) Footnote text.
   __________
   Next paragraph.
   ```
   The separator pair acts as open/close delimiters. If the opening separator appears right after a heading with no content yet, the footnote is a title footnote; otherwise it belongs to the preceding content paragraph.

3. `chunking.py` — splits long segment content into ≤800-char subchunks at line boundaries. Each line in the Markdown is a complete paragraph, so the split never cuts a paragraph mid-way. Blank lines are ignored by the parser. **800 chars is the ceiling** — calibrated to typical item length across the 4 books (median 440-1600 chars, p90 up to ~6600 chars), not to the embedding model's technical limit (`BAAI/bge-m3` supports up to 8192 tokens); larger chunks would dilute retrieval precision by mixing multiple ideas into one embedding.
4. `parsing_pipeline.py` — orchestrates all books; maps filenames to canonical book names via `BOOK_NAME_MAP`. `trecho_diario.md` is intentionally absent from `BOOK_NAME_MAP` and silently skipped here — it's consumed separately by `src/rag/evangelho.py`, not through this pipeline (see Daily passage under RAG Layer).

**Numbered items** (`123. text`) are the primary structural unit in all books:
- **Livro dos Espíritos, Livro dos Médiuns** — single global sequence (1 to N across the whole book)
- **Evangelho segundo o Espiritismo, Céu e Inferno** — per-chapter sequences (reset to 1 at each chapter heading)

The Markdown source files (`data/markdown_files/`) are hand-reviewed and corrected — treat them as authoritative. Do not regenerate them from PDFs.

### Ingestion Layer (`src/ingestion/`)

Fully implemented. Run once (or re-run to rebuild the vector store).

- `embeddings.py` — wraps `SentenceTransformer` (`BAAI/bge-m3`); module-level singleton. Calls `huggingface_hub.login()` on startup if `HF_TOKEN` is set in env.
- `vectorstore.py` — wraps ChromaDB. Methods: `upsert`, `query` (semantic), `get_by_filter` (metadata-only lookup)
- `pipeline.py` — loads JSON → batches of 64 → embeds → upserts. `_build_document` appends footnotes after content, capped at 3000 chars total so the embedding model is never truncated. Full footnote text is always available in the JSON metadata.

Document ID format: `{book_filename_stem}_{item_number}_{subchunk_index}` — stable across re-runs (upsert is idempotent).

### RAG Layer (`src/rag/`)

Fully implemented. Each mode has a dedicated prompt file and a pipeline file.

**Shared infrastructure:**
- `retriever.py` — `retrieve(query, top_k)`: semantic search filtered by cosine distance threshold. `retrieve_by_item(book, item_number)`: metadata-only lookup returning all subchunks of a specific item. Both strip the ingestion-baked `\n[Nota N] ...` footnote suffix off `content` before returning, exposing it separately as `footnote_context` (empty string if none) — see "Footnote handling" below.
- `mode_detector.py` — `detect_suggested_mode(question)`: regex-based detection of study intent (e.g. "questão 132", "item 45") → returns `"estudar_obra"` or `None`. No LLM cost.

**Footnote handling:** footnotes are baked into each chunk's stored `content` at ingestion time (see Ingestion Layer above), for embedding purposes only. `retriever.py` strips that suffix back off on every read so it never leaks into displayed text, LLM prompts, or citation excerpts — the stripped text is exposed as `footnote_context` for callers that want it as grounding material (currently only Explicador).

**Explicador agent** (`/study`):
- `explicador_prompt.py` — Socratic tutor system prompt. Output JSON: `{"contexto", "conceitos_chave": [...], "perguntas": [...]}`. `contexto` (3-6 sentences) explains where the item fits in the doctrine and may include well-known historical/cultural background using general knowledge (e.g. who the Pharisees were) — but doctrine itself stays strictly grounded in the retrieved text, and the response must make that distinction legible in prose ("Historicamente, os fariseus eram... O texto, por sua vez, mostra que..."). `conceitos_chave` definitions may include a short clarifying gloss, not just a literal one-sentence extraction. It is still forbidden to summarize or paraphrase the passage itself, and to personify "o Espiritismo" as an agent that does/values things — attribute doctrinal claims to the passage, the text, or Kardec. `parse_explicador_json` returns `(contexto, conceitos_chave, perguntas)`.
- `explicador.py` — pipeline: direct item lookup via `retrieve_by_item` → semantic related items → Explicador LLM (fed the main passage's `footnote_context` as extra grounding) → `curar()` for related item annotation. Returns `original_text`, `contexto`, `conceitos_chave`, `perguntas`, `related_items`, `sources`, `generation_failed`. `perguntas` is still generated but the frontend no longer displays it for "Estudar uma Obra" (see API Layer).

**Curador agent** (called by Explicador and Reflexivo):
- `curador_prompt.py` — given the main passage and up to 3 candidate chunks, asks the LLM to select 1–3 doctrinally connected candidates and write one Portuguese sentence explaining each connection. Output JSON: `[{"index": N, "conexao": "..."}]`. `parse_curador_json` returns list of `{"index", "conexao"}`. Falls back to empty list on parse failure.
- `curador.py` — `curar(main_text, candidates)`: calls Curador LLM → merges `conexao` (and `chapter`, from the candidate chunk's metadata) into candidate metadata. On any failure, falls back to the raw candidates without `conexao` (never breaks the calling pipeline). `chapter` is required so the frontend's related-items click-through can disambiguate books that reset item numbering per chapter (Evangelho, Céu e Inferno) — `book` + `item_number` alone is ambiguous there.

**Reflexivo agent** (`/reflect`):
- `reflect_prompt.py` — tone-adaptive system prompt with a hard no-advice constraint. A keyword list (`vozes`, `sombras`, `pânico`, etc.) triggers an optional medical/mediumship caveat. Output JSON: `{"opening", "doctrine_connection", "reflection_questions": [...]}`. `parse_reflect_json` extracts the three fields.
- `reflect.py` — pipeline: semantic retrieval (top 5) → primary chunks ([:2]) used for LLM → complementary chunks ([2:5]) passed to `curar()`. Returns `opening`, `doctrine_connection`, `reflection_questions`, `complementary_items`, `sources`, `not_found`, `generation_failed`.

**Generator** (`/chat`):
- `prompt.py` — system prompt + message builder for `/chat`. Rules: answer strictly from retrieved passages; separate original text from AI explanation; never close with unsolicited advice or a suggested course of action (only if the user's question asks for one directly); never personify "o Espiritismo" as an agent; may optionally weave in a reflective question when it fits naturally (distinct from the advice prohibition — questions aren't advice).
- `generator.py` — optional query condensation (Groq) → retrieval → prompt → Groq LLM answer. Returns `answer`, `sources` (each with `book`, `chapter`, `item_number`, `excerpt` — the retrieved chunk text, used by the frontend's citation-chip modal), `not_found`.

**Daily passage** (`evangelho.py`): sourced from `data/markdown_files/trecho_diario.md` — a curated 27-chapter subset of O Evangelho (hand-picked items per chapter, not the full book), deliberately kept separate from the main ChromaDB collection so it never pollutes `/chat`/`/reflect`/`/study`'s semantic search. Parsed once with the existing `parse_md_to_json` parser and cached in memory (`_get_chunks()`), no ChromaDB involved. `get_daily_passage()` seeds `random` with today's ISO date, picks a random chapter then a random item within it, and joins all of that item's subchunks (space-separated) into the full displayed text — not just the first subchunk. No LLM.

**Reflect mode guardrails:** The system prompt contains a verbatim Portuguese prohibition against advice, suggestions, medication recommendations, or any course of action. A keyword list triggers an optional one-sentence medical/mediumship caveat appended to the response. Same "never personify Espiritismo" rule as `/chat` and Explicador applies here too.

### API Layer (`src/api/`)

Fully implemented.

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Tirar uma Dúvida — returns `answer`, `sources` (with `excerpt`), `not_found`, `suggested_mode` |
| `GET` | `/paths` | List curated learning path summaries |
| `GET` | `/paths/{path_id}` | Full path detail with steps |
| `POST` | `/study` | Estudar uma Obra — requires `book` + `item_number`; returns `original_text`, `contexto`, `conceitos_chave`, `perguntas`, `related_items`, `sources` |
| `POST` | `/reflect` | Refletir sobre uma Situação — requires `situation` text |
| `GET` | `/evangelho` | Daily passage from O Evangelho (curated `trecho_diario.md` subset; 503 if the file can't be read) |
| `GET` | `/health` | `{"status": "ok"}` |

The API is stateless — clients own conversation history. `/chat` and `/reflect` accept `history` / `conversation_history` but the server does not store it.

**`suggested_mode` on `/chat`:** when the question looks like a specific item lookup (e.g. "explique a questão 132"), the response includes `suggested_mode: "estudar_obra"` as a hint for the client to surface the `/study` button.

**`Source`/`StudySource` schema** (used by `/chat`'s `sources` and `/reflect`'s `sources`):
```json
{ "book": "...", "chapter": "...", "item_number": "...", "excerpt": "..." }
```
`excerpt` is the retrieved chunk's text (footnote-stripped), used by the frontend's clickable citation chip → `SourceModal`. `null` for legacy/unpopulated cases.

**`RelatedItem` schema** (used in both `/study` `related_items` and `/reflect` `complementary_items`):
```json
{ "book": "...", "chapter": "...", "item_number": "...", "preview": "...", "conexao": "..." }
```
`conexao` is a one-sentence Portuguese explanation of the doctrinal connection to the main passage, generated by the Curador agent. It is `null` when the Curador call fails. `chapter` disambiguates per-chapter item numbering (see Curador agent above) and is used by the frontend's `RelatedItemsModal` when the user clicks through to the full item.

### Curated Learning Paths (`data/paths/`)

JSON files, one per path. The API serves them statically — no database, client owns progress tracking. Schema: `id`, `title`, `description`, `level` (`curioso` / `estudante` / `aprofundado`), `steps[]` (each step: `book`, `item_number`, `label`).

## Data

- `data/books/` — original PDFs (gitignored)
- `data/markdown_files/` — hand-reviewed Markdown source (committed, do not overwrite)
- `data/json_files/` — output of the parsing pipeline (regenerable)
- `data/embeddings/` — vector DB (gitignored, regenerable)
- `data/paths/` — curated learning path JSON files (committed)
