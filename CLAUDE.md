# CLAUDE.md

Guidance for Claude Code working in this repo. These instructions override default behavior.

## Project Overview

**Kardec Study Assistant** is the backend of *Dialogando com a Doutrina* — a RAG study companion for Allan Kardec's Spiritist works. It lowers the barrier for people with limited time or difficulty with the original language; it does not replace reading the works.

**The core rule that governs everything:** responses must be **strictly retrieval-grounded** (hallucinated doctrine is unacceptable) and must **visibly separate what comes from the source text from what comes from the AI**. Every prompt and pipeline in `src/rag/` exists to enforce this.

Deep implementation detail (per-agent output shapes, parsing internals, schemas) lives in [docs/architecture.md](docs/architecture.md) — read it when you touch a specific layer. This file is the orientation + the rules.

### MVP modes

| # | Mode | Endpoint | Returns |
|---|---|---|---|
| 1 | **Estudar uma Obra** | `POST /study` | Original text + doctrinal context + key concepts + Socratic questions + curated related refs |
| 2 | **Tirar uma Dúvida** | `POST /chat` | Grounded answer + excerpts + sources + suggested mode |
| 3 | **Refletir sobre uma Situação** — ⚠️ **switched off** | ~~`POST /reflect`~~ | Retrieval eval showed it answers lived suffering with reincarnation passages, unfixable by embedding-model swap. Code is disconnected, not deleted. See [docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md](docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md). |
| 4 | **Abrir o Evangelho** | `GET /evangelho` | Daily passage (deterministic, no LLM) |

Supporting: `GET /paths`, `GET /paths/{id}`, `GET /health`.

## Environment

- Package manager **uv** (`uv sync --group dev`), Python 3.12+
- **Dependency groups matter for deploy:** `sentence-transformers` (and with it
  torch + CUDA, ~4.7 GB) lives in the `ingest` group, not in the runtime
  dependencies. The container runs `uv sync --no-dev` and must never install it —
  see [docs/deploy.md](docs/deploy.md).
- Requires `.env` with `TOGETHER_API_KEY` (Together, OpenAI-compatible endpoint).
  `LLM_PROVIDER` also accepts `openrouter` and `google`.
- Optional prose lane: `PROSE_PROVIDER=ollama` routes `/chat` and `/study` prose
  to `ia-espirita/riv-ai-v2` (local Ollama). Unset = single provider, today's
  behavior. Reflexivo (currently switched off, see below) and every
  structured-JSON agent (Curador, orchestrator, condenser, sensitivity) always
  stay on `LLM_PROVIDER`.

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
- **`src/ingestion/`** — `embeddings.py`, `vectorstore.py` (ChromaDB), `pipeline.py`. `encode()` is the single seam every embedding passes through and dispatches on `EMBEDDING_PROVIDER`: unset = `BAAI/bge-m3` in-process (dev), or a key of `EMBEDDING_PROVIDERS` (`openrouter`/`deepinfra`/`novita`) to call **the same model** over HTTP (production). Parity measured 2026-07-27: cosine 0.999994 vs the stored vectors, 100% top-5 overlap — the index and the calibrated thresholds survive the switch. `sentence_transformers` is imported *inside* `_get_model()` so a hosted-only image can drop the dependency; do not hoist that import. Document ID: `{book_stem}_{item_number}_{subchunk_index}` (stable, upsert-idempotent).
- **`src/rag/`** — one prompt file + one pipeline file per mode. Agents: **Explicador** (`/study`), **Reflexivo** (`reflect.py`/`reflect_prompt.py` — code intact but **not routed**, see MVP modes table above), **Curador** (called by Explicador and, when reconnected, Reflexivo), **Generator** (`/chat`), **Orchestrator** (mode-nudge classifier). Shared: `retriever.py`, `mode_detector.py`, `query_condenser.py`, `evangelho.py`, `crisis.py` (see Rules below).
- **`src/api/`** — FastAPI routes (`routes.py`), pydantic schemas (`schemas.py`). Stateless: clients own conversation history; `/chat` accepts it but nothing is stored. (`ReflectRequest`/`ReflectResponse` schemas still exist, inert, for the same reason.)

## Rules (these steer behavior — do not violate)

- **Grounding & attribution:** never invent doctrine; answer only from retrieved passages; keep source text visibly separate from AI explanation. Historical/cultural background from general knowledge is allowed *only* when the prose makes the distinction legible ("Historicamente… O texto, por sua vez…").
- **Never personify "o Espiritismo"** as an agent that does/values things — attribute doctrinal claims to the passage, the text, or Kardec. Applies to Explicador, Generator, and Reflexivo (currently switched off, see MVP modes table above).
- **Crisis handling is a shared layer, independent of any single mode — it does not live or die with Reflexivo.** It is its own module, `src/rag/crisis.py`, imported by every consumer (`/chat`'s `generator.py`, the `orchestrator.py` nudge classifier, and `reflect.py`/`reflect_prompt.py` when Reflexivo is reconnected) precisely so that switching a mode off can never switch this off with it. It is deterministic, never left to the LLM: `needs_crisis_note()` (**first-person** suicidal-ideation/self-harm cues, accent-tolerant) short-circuits to a fixed crisis exit (`CRISIS_EXIT_MESSAGE`, CVV 188 / SAMU 192) **in code, before any retrieval or LLM call** — no doctrinal answer, no citations, no chips. **Topic-level mentions** (`mentions_suicide_topic()`: "suicídio" as subject, no ideation) do NOT exit: the question is answered from the works and `CRISIS_NOTE` (CVV 188) is appended to the answer **in code, always**; keep every ideation phrasing that contains a topic word listed in `CRISIS_KEYWORDS` so it is caught before the topic path. This is the guaranteed floor of the **sensitivity tiering** layer (`normal | abalo | crise`, see `src/rag/sensitivity.py`): a small-LLM `classify_sensitivity` runs concurrently with retrieval and can only *escalate* handling (`final = max(keyword_crise, llm_level)`), never lower it. On `abalo`, the darkest O Céu e o Inferno testimony chapters (`SENSITIVE_CHAPTERS`) **and any chunk whose content matches suicide-adjacent language** (`_SENSITIVE_CONTENT_RE`, book-agnostic — catches ESE's "abreviar as misérias") are filtered from retrieval, the prompt turns gentle, and follow-up chips are suppressed; on `crise` (keyword or LLM), the fixed exit is returned. `safety_level` is exposed on responses and the mode nudge is suppressed on `crise`. `CLINICAL_KEYWORDS`/`needs_medical_caveat()` (the medical/mediumship caveat trigger) live here too, since `/chat` depends on them independent of Reflexivo.
- **⚠️ Reflexivo is currently switched off** (see MVP modes table above) — the rest of this bullet describes it as it behaves when reconnected, not current production behavior: hard no-advice constraint (no suggestions, no course of action unless directly asked); the medical/mediumship caveat text (`_CAVEAT_INSTRUCTION` in `reflect_prompt.py`) is triggered by `needs_medical_caveat()` from `crisis.py`; after `CAP_ROUNDS` (5) rounds it forces a closing; 1–3 reflection questions per turn (fewer, sharper).
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
| `GET` | `/evangelho` | daily passage (503 if the file can't be read) |
| `GET` | `/paths`, `/paths/{id}` | curated learning paths (static JSON in `data/paths/`) |
| `GET` | `/health` | `{"status": "ok"}` |

`POST /reflect` is absent from this table because the route is commented out (Reflexivo is switched off, see MVP modes table above); it currently returns 404 by absence of route, not a deliberate 503/"unavailable" response.

Response schemas (`Source`, `StudySource`, `RelatedItem`, …) are defined in `src/api/schemas.py` — read there, don't duplicate here.

## Data

- `data/books/` — original PDFs (gitignored)
- `data/markdown_files/` — **hand-reviewed, authoritative source. Do not overwrite or regenerate from PDFs.**
- `data/json_files/` — parser output (regenerable)
- `data/embeddings/` — vector DB (gitignored, regenerable)
- `data/paths/` — curated learning-path JSON (committed)
