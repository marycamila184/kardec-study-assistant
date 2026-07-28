# CLAUDE.md

Guidance for Claude Code working in this repo. These instructions override default behavior.

## Project Overview

**Kardec Study Assistant** is the backend of *Dialogando com a Doutrina* — a RAG study companion for Allan Kardec's Spiritist works. It lowers the barrier for people with limited time or difficulty with the original language; it does not replace reading the works.

**The core rule that governs everything:** responses must be **strictly retrieval-grounded** (hallucinated doctrine is unacceptable) and must **visibly separate what comes from the source text from what comes from the AI**. Every prompt and pipeline in `src/rag/` exists to enforce this.

This file is the orientation + the rules. Everything else lives in `docs/`:

| Onde | O quê | Quando ler |
|---|---|---|
| [docs/architecture.md](docs/architecture.md) | Referência profunda: formas de saída por agente, internos do parsing, schemas, as duas vias de provedor, limiares calibrados | Ao mexer numa camada específica |
| [src/rag/prompts/](src/rag/prompts/README.md) | **Os prompts**, um arquivo `.md` por peça, carregados em tempo de execução. O README de lá diz o que pode virar regra de prompt e o que tem de ser código | Ao ajustar tom, formato ou o que o modelo deve dizer |
| [docs/superpowers/specs/README.md](docs/superpowers/specs/README.md) | **Índice das 42 specs** por assunto, marcando as superadas e as declinadas | Antes de refazer uma decisão — para saber se ela já foi tomada, e por quê |
| [docs/superpowers/plans/](docs/superpowers/plans/) | Planos de implementação, um por lote de trabalho | Ao executar um plano existente |
| [docs/deploy.md](docs/deploy.md) | Comandos e restrições de deploy (Cloud Run + Vercel) | Ao publicar |
| [docs/superpowers/2026-07-25-handoff.md](docs/superpowers/2026-07-25-handoff.md) | Handoff de estado do projeto | Ao retomar o contexto de longe |

### Modes and endpoints

| Mode | Endpoint | State |
|---|---|---|
| **Estudar uma Obra** | `POST /study` | Live. Requires `book` + `item_number`. `POST /study/stream` returns the same answer over SSE (`source` / `token` / `done`); `/study` keeps its contract and stays the recovery path |
| **Tirar uma Dúvida** | `POST /chat` | Live. `POST /chat/stream` returns the same answer over SSE (`token` / `done`); `/chat` keeps its contract and stays the recovery path |
| **Refletir sobre uma Situação** | ~~`POST /reflect`~~ | ⚠️ **Switched off.** Retrieval eval showed it answers lived suffering with reincarnation passages, unfixable by embedding-model swap. Code disconnected, not deleted; the route is commented out, so it 404s by absence rather than a deliberate 503. See [the design](docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md) |
| **Abrir o Evangelho** | `GET /evangelho` | Live. Deterministic, no LLM (503 if the file can't be read) |

Supporting: `GET /paths`, `GET /paths/{id}`, `GET /health`.

Request and response shapes live in `src/api/schemas.py` — read there, don't duplicate. Field-level semantics (`suggested_mode`, `safety_level`, `Source`, `RelatedItem`) are in [docs/architecture.md](docs/architecture.md).

## Environment

- Package manager **uv** (`uv sync --group dev`), Python 3.12+
- **Dependency groups matter for deploy:** `sentence-transformers` (and with it torch + CUDA, ~4.7 GB) lives in the `ingest` group, not in the runtime dependencies. The container runs `uv sync --no-dev` and must never install it — see [docs/deploy.md](docs/deploy.md).
- Requires `.env` with `TOGETHER_API_KEY`. `LLM_PROVIDER` also accepts `openrouter` and `google`; `PROSE_PROVIDER=ollama` routes `/chat` and `/study` prose to a local model. Which agent runs on which lane is in [docs/architecture.md](docs/architecture.md) — structured-JSON agents (Curador, orchestrator, condenser, sensitivity) always stay on `LLM_PROVIDER`.

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

- **`src/parsing/`** — cleans LlamaCloud artifacts and parses Markdown into structured chunks. Numbered items (`123. text`) are the primary unit.
- **`src/ingestion/`** — embeds and indexes into ChromaDB. `encode()` in `embeddings.py` is the single seam every embedding passes through, dispatching on `EMBEDDING_PROVIDER` between the in-process model (dev) and **the same model** over HTTP (production). **Do not hoist the `sentence_transformers` import out of `_get_model()`** — that pulls torch into the container image and undoes the 4.7 GB the hosted lane exists to save.
- **`src/rag/prompts/*.md`** — every prompt, loaded at runtime by `prompt_files.load()`. Edit the file, restart the API; there is no second copy in the Python. `crisis.py` is deliberately NOT here — that text is decided in code before any model call.
- **`src/rag/`** — one prompt file + one pipeline file per mode. Agents: **Explicador** (`/study`), **Reflexivo** (intact but **not routed**), **Curador**, **Generator** (`/chat`), **Orchestrator** (mode-nudge classifier). Shared: `retriever.py`, `mode_detector.py`, `query_condenser.py`, `evangelho.py`, `stream_buffer.py`, `json_stream.py`, `crisis.py` (see Rules below).
- **`src/api/`** — FastAPI routes (`routes.py`), pydantic schemas (`schemas.py`). Stateless: clients own conversation history; `/chat` accepts it but nothing is stored.

## Rules (these steer behavior — do not violate)

- **Grounding & attribution:** never invent doctrine; answer only from retrieved passages; keep source text visibly separate from AI explanation. Historical/cultural background from general knowledge is allowed *only* when the prose makes the distinction legible ("Historicamente… O texto, por sua vez…").
- **Never personify "o Espiritismo"** as an agent that does/values things — attribute doctrinal claims to the passage, the text, or Kardec. Applies to Explicador, Generator, and Reflexivo (currently switched off).
- **Crisis handling is a shared layer, independent of any single mode — it does not live or die with Reflexivo.** It is its own module, `src/rag/crisis.py`, imported by every consumer (`/chat`'s `generator.py`, the `orchestrator.py` nudge classifier, and `reflect.py`/`reflect_prompt.py` when Reflexivo is reconnected) precisely so that switching a mode off can never switch this off with it. It is deterministic, never left to the LLM: `needs_crisis_note()` (**first-person** suicidal-ideation/self-harm cues, accent-tolerant) short-circuits to a fixed crisis exit (`CRISIS_EXIT_MESSAGE`, CVV 188 / SAMU 192) **in code, before any retrieval or LLM call** — no doctrinal answer, no citations, no chips. **Topic-level mentions** (`mentions_suicide_topic()`: "suicídio" as subject, no ideation) do NOT exit: the question is answered from the works and `CRISIS_NOTE` (CVV 188) is appended to the answer **in code, always**; keep every ideation phrasing that contains a topic word listed in `CRISIS_KEYWORDS` so it is caught before the topic path. This is the guaranteed floor of the **sensitivity tiering** layer (`normal | abalo | crise`, see `src/rag/sensitivity.py`): a small-LLM `classify_sensitivity` runs concurrently with retrieval and can only *escalate* handling (`final = max(keyword_crise, llm_level)`), never lower it. On `abalo`, the darkest O Céu e o Inferno testimony chapters (`SENSITIVE_CHAPTERS`) **and any chunk whose content matches suicide-adjacent language** (`_SENSITIVE_CONTENT_RE`, book-agnostic — catches ESE's "abreviar as misérias") are filtered from retrieval, the prompt turns gentle, and follow-up chips are suppressed; on `crise` (keyword or LLM), the fixed exit is returned. `safety_level` is exposed on responses and the mode nudge is suppressed on `crise`. `CLINICAL_KEYWORDS`/`needs_medical_caveat()` (the medical/mediumship caveat trigger) live here too, since `/chat` depends on them independent of Reflexivo.
- **The crisis exit never streams.** It is fixed text decided in code before any model call, and arrives whole and immediate — a crisis message appearing letter by letter would be cruel and pointless. Small talk, the size cap and the rate limit likewise all answer before a stream is ever opened.
- **⚠️ Reflexivo is currently switched off** (see the modes table above) — the rest of this bullet describes it as it behaves when reconnected, not current production behavior: hard no-advice constraint (no suggestions, no course of action unless directly asked); the medical/mediumship caveat text (`_CAVEAT_INSTRUCTION` in `reflect_prompt.py`) is triggered by `needs_medical_caveat()` from `crisis.py`; after `CAP_ROUNDS` (5) rounds it forces a closing; 1–3 reflection questions per turn (fewer, sharper).
- **`/chat` trailer markers:** the model ends its answer with machine-readable `[FONTES: 1, 3]` (passages actually used; empty = no sources) and `[SEGUIR: q1 | q2]` (two follow-up chips). `_strip_trailing_markers` removes them (tolerant of malformed/`/FONTES:` variants). The answer text must **never end with a question** — follow-ups live only in `[SEGUIR]`.
- **No streamed token may ever contain `FONTES` or `SEGUIR`.** `stream_buffer.py` holds back any text that could still grow into a trailer marker, and the `done` event carries the fully post-processed answer — it is the source of truth, so a streamed response ends up identical to what `POST /chat` returns.
- **No streamed `/study` token may ever contain JSON syntax.** Explicador stays pinned to the JSON lane, so `json_stream.py` reads the `contexto` field out of the response as it arrives and holds back anything that could still be an incomplete escape — half a `\uXXXX` must never reach the screen as literal text. Same contract as `/chat`: `done` is parsed from the accumulated JSON with the same `_parse` the non-streaming lane uses, so a streamed `/study` is identical to `POST /study`. The `source` event comes before any token so the passage is on screen before the explanation of it.
- **Small talk:** `is_smalltalk()` short-circuits pure acknowledgments ("obrigada", "valeu") to a brief warm reply with no retrieval, no sources, no suggestions.
- **Mode detection / orchestrator:** `mode_detector.py` extracts item references by regex — "questão N" / "Q. N" default to **O Livro dos Espíritos** (only work whose entries are numbered questões, 1-1019); "item N" leaves book `null`. All patterns accent-tolerant and must stay in sync between detection and extraction. `orchestrator.classify_intent()` is a small-LLM classifier that suggests switching mode (non-destructive nudge button); it runs concurrently with answer generation, is suppressed on crisis/small-talk, and never nudges toward the current mode.
- **Footnotes** are baked into stored `content` at ingestion (for embedding only) and **stripped on every read** in `retriever.py`, exposed separately as `footnote_context` — they never leak into displayed text, prompts, or citations.
- **Curador** must carry `chapter` on related items — `book` + `item_number` is ambiguous for Evangelho and Céu e Inferno (per-chapter numbering).
- **Daily passage** (`evangelho.py`) is sourced from the curated `data/markdown_files/trecho_diario.md`, kept out of the main ChromaDB collection so it never pollutes semantic search; deterministic (seeded by today's date), no LLM.

## Data

- `data/books/` — original PDFs (gitignored)
- `data/markdown_files/` — **hand-reviewed, authoritative source. Do not overwrite or regenerate from PDFs.**
- `data/json_files/` — parser output (regenerable)
- `data/embeddings/` — vector DB (gitignored, regenerable)
- `data/paths/` — curated learning-path JSON (committed)
