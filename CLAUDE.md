# CLAUDE.md

Guidance for Claude Code working in this repo. These instructions override default behavior.

## Project Overview

**Kardec Study Assistant** is the backend of *Dialogando com a Doutrina* — a RAG study companion for Allan Kardec's Spiritist works. It lowers the barrier for people with limited time or difficulty with the original language; it does not replace reading the works.

**The core rule that governs everything:** responses must be **strictly retrieval-grounded** (hallucinated doctrine is unacceptable) and must **visibly separate what comes from the source text from what comes from the AI**. Every prompt and pipeline in `src/rag/` exists to enforce this.

Deep implementation detail (per-agent output shapes, parsing internals, schemas) lives in [docs/architecture.md](docs/architecture.md) — read it when you touch a specific layer. This file is the orientation + the rules.

### MVP modes (all implemented)

| # | Mode | Endpoint | Returns |
|---|---|---|---|
| 1 | **Estudar uma Obra** | `POST /study` | Original text + doctrinal context + key concepts + Socratic questions + curated related refs |
| 2 | **Tirar uma Dúvida** | `POST /chat` | Grounded answer + excerpts + sources + suggested mode |
| 3 | **Refletir sobre uma Situação** | `POST /reflect` | Tone-adaptive opening + doctrinal connection + reflection questions + complementary readings |
| 4 | **Abrir o Evangelho** | `GET /evangelho` | Daily passage (deterministic, no LLM) |

Supporting: `GET /paths`, `GET /paths/{id}`, `GET /health`.

## Environment

- Package manager **uv** (`uv sync --group dev`), Python 3.12+
- Requires `.env` with `GROQ_API_KEY` (Groq, OpenAI-compatible endpoint)

## Commands

```bash
uv sync --group dev                              # install
uv run python -m src.parsing.parsing_pipeline    # parse: MD → JSON
uv run python -m src.ingestion.pipeline          # ingest: JSON → ChromaDB
uv run fastapi dev src/api/main.py               # run API (dev)
uv run black src/ && uv run isort src/           # format
uv run pytest                                    # tests
```

## Architecture

One-directional pipeline:

```
PDFs → (LlamaCloud) → data/markdown_files/*.md
   → src/parsing/  (clean + parse) → data/json_files/*.json
   → src/ingestion/ (embed + index) → data/embeddings/  (vector store, gitignored)
   → src/rag/ (retrieve + prompt + generate)
   → src/api/ (FastAPI endpoints)
```

- **`src/parsing/`** — cleans LlamaCloud artifacts and parses Markdown into structured chunks (`book`, `chapter`, `item_number`, `content`, per-paragraph `footnotes`, `title_footnotes`, …). Numbered items (`123. text`) are the primary unit. Long content is split into ≤800-char subchunks at line boundaries. See docs/architecture.md for the chunk schema and footnote format.
- **`src/ingestion/`** — `embeddings.py` (`BAAI/bge-m3` singleton), `vectorstore.py` (ChromaDB), `pipeline.py`. Document ID: `{book_stem}_{item_number}_{subchunk_index}` (stable, upsert-idempotent).
- **`src/rag/`** — one prompt file + one pipeline file per mode. Agents: **Explicador** (`/study`), **Reflexivo** (`/reflect`), **Curador** (called by both), **Generator** (`/chat`), **Orchestrator** (mode-nudge classifier). Shared: `retriever.py`, `mode_detector.py`, `query_condenser.py`, `evangelho.py`.
- **`src/api/`** — FastAPI routes (`routes.py`), pydantic schemas (`schemas.py`). Stateless: clients own conversation history; `/chat` and `/reflect` accept it but nothing is stored.

## Rules (these steer behavior — do not violate)

- **Grounding & attribution:** never invent doctrine; answer only from retrieved passages; keep source text visibly separate from AI explanation. Historical/cultural background from general knowledge is allowed *only* when the prose makes the distinction legible ("Historicamente… O texto, por sua vez…").
- **Never personify "o Espiritismo"** as an agent that does/values things — attribute doctrinal claims to the passage, the text, or Kardec. Applies to Explicador, Reflexivo, and Generator.
- **Crisis handling is deterministic, never left to the LLM:** `needs_crisis_note()` (suicidal-ideation/self-harm cues, accent-tolerant) short-circuits both `/chat` and `/reflect` to a fixed crisis exit (`CRISIS_EXIT_MESSAGE`, CVV 188 / SAMU 192) **in code, before any retrieval or LLM call** — no doctrinal answer, no citations, no chips. This is the guaranteed floor of the **sensitivity tiering** layer (`normal | abalo | crise`, see `src/rag/sensitivity.py`): a small-LLM `classify_sensitivity` runs concurrently with retrieval and can only *escalate* handling (`final = max(keyword_crise, llm_level)`), never lower it. On `abalo`, the darkest O Céu e o Inferno testimony chapters (`SENSITIVE_CHAPTERS`) are filtered from retrieval, the prompt turns gentle, and follow-up chips are suppressed; on `crise` (keyword or LLM), the fixed exit is returned. `safety_level` is exposed on both responses and the mode nudge is suppressed on `crise`.
- **Reflect has a hard no-advice constraint** (no suggestions, no course of action unless directly asked). Optional medical/mediumship caveat on `CLINICAL_KEYWORDS`. After `CAP_ROUNDS` (5) rounds it forces a closing. 1–3 reflection questions per turn (fewer, sharper).
- **`/chat` trailer markers:** the model ends its answer with machine-readable `[FONTES: 1, 3]` (passages actually used; empty = no sources) and `[SEGUIR: q1 | q2]` (two follow-up chips). `_strip_trailing_markers` removes them (tolerant of malformed/`/FONTES:` variants). The answer text must **never end with a question** — follow-ups live only in `[SEGUIR]`.
- **Small talk:** `is_smalltalk()` short-circuits pure acknowledgments ("obrigada", "valeu") to a brief warm reply with no retrieval, no sources, no suggestions.
- **Mode detection / orchestrator:** `mode_detector.py` extracts item references by regex — "questão N" / "Q. N" default to **O Livro dos Espíritos** (only work whose entries are numbered questões, 1-1019); "item N" leaves book `null`. All patterns accent-tolerant and must stay in sync between detection and extraction. `orchestrator.classify_intent()` is a small-LLM classifier that suggests switching mode (non-destructive nudge button); it runs concurrently with answer generation, is suppressed on crisis/small-talk, and never nudges toward the current mode.
- **Footnotes** are baked into stored `content` at ingestion (for embedding only) and **stripped on every read** in `retriever.py`, exposed separately as `footnote_context` — they never leak into displayed text, prompts, or citations.
- **Curador** must carry `chapter` on related items — `book` + `item_number` is ambiguous for Evangelho and Céu e Inferno (per-chapter numbering).
- **Daily passage** (`evangelho.py`) is sourced from the curated `data/markdown_files/trecho_diario.md`, kept out of the main ChromaDB collection so it never pollutes semantic search; deterministic (seeded by today's date), no LLM.

## API endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/chat` | `answer`, `sources` (with `excerpt`), `suggested_questions`, `not_found`, `suggested_mode` (+ `suggested_item_number`/`suggested_book` for `estudar_obra`) |
| `POST` | `/study` | requires `book` + `item_number`; returns `original_text`, `contexto`, `conceitos_chave`, `perguntas`, `related_items`, `sources` |
| `POST` | `/reflect` | requires `situation`; tone-adaptive; carries `suggested_mode` like `/chat` |
| `GET` | `/evangelho` | daily passage (503 if the file can't be read) |
| `GET` | `/paths`, `/paths/{id}` | curated learning paths (static JSON in `data/paths/`) |
| `GET` | `/health` | `{"status": "ok"}` |

Response schemas (`Source`, `StudySource`, `RelatedItem`, …) are defined in `src/api/schemas.py` — read there, don't duplicate here.

## Data

- `data/books/` — original PDFs (gitignored)
- `data/markdown_files/` — **hand-reviewed, authoritative source. Do not overwrite or regenerate from PDFs.**
- `data/json_files/` — parser output (regenerable)
- `data/embeddings/` — vector DB (gitignored, regenerable)
- `data/paths/` — curated learning-path JSON (committed)
