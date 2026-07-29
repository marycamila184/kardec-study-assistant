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
| [docs/superpowers/specs/README.md](docs/superpowers/specs/README.md) | **Índice das specs** por assunto, marcando as superadas e as declinadas | Antes de refazer uma decisão — para saber se ela já foi tomada, e por quê |
| [docs/superpowers/plans/](docs/superpowers/plans/) | Planos de implementação, um por lote de trabalho | Ao executar um plano existente |
| [docs/deploy.md](docs/deploy.md) | Comandos e restrições de deploy (Cloud Run + Vercel) | Ao publicar |
| [docs/superpowers/2026-07-25-handoff.md](docs/superpowers/2026-07-25-handoff.md) | Handoff de estado do projeto | Ao retomar o contexto de longe |

### Modes and endpoints

| Mode | Endpoint | State |
|---|---|---|
| **Estudar uma Obra** | `POST /study` | Live, for the paths where the chapter is known: **trilhas**, the daily passage, the source handoff and the related-items modal. Requires `book` + `item_number`. `POST /study/stream` returns the same answer over SSE (`source` / `token` / `done`); `/study` keeps its contract and stays the recovery path |
| **Estudo livre** (digitar em Explorar) | `POST /chat` | Live. `_direct_item_chunks` resolves a named item and the response carries `studied_item`, which the frontend renders as the **Da Obra** block — free study keeps the source/AI separation while gaining the guards and the profile axes `/study` lacks. Item lookup is skipped for Evangelho, whose numbering repeats per chapter; that case belongs to `/study`, which is given the chapter |
| **Tirar uma Dúvida** | `POST /chat` | Live. `POST /chat/stream` returns the same answer over SSE (`token` / `done`); `/chat` keeps its contract and stays the recovery path |
| **Refletir sobre uma Situação** | ~~`POST /reflect`~~ | ⚠️ **Switched off.** Retrieval eval showed it answers lived suffering with reincarnation passages, unfixable by embedding-model swap. Code disconnected, not deleted; the route is commented out, so it 404s by absence rather than a deliberate 503. See [the design](docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md) |
| **Abrir o Evangelho** | `GET /evangelho` | Live. Deterministic, no LLM (503 if the file can't be read) |

Supporting: `GET /paths`, `GET /paths/{id}`, `GET /health`, `POST /feedback` (a thumbs up/down on one answer, joined to its turn by `turn_id`; 204, no body, no rate limit).

Request and response shapes live in `src/api/schemas.py` — read there, don't duplicate. Field-level semantics (`suggested_mode`, `safety_level`, `turn_id`, `Source`, `RelatedItem`) are in [docs/architecture.md](docs/architecture.md).

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
- **`src/rag/`** — one prompt file + one pipeline file per mode. Agents: **Explicador** (`/study`), **Reflexivo** (intact but **not routed**), **Curador**, **Generator** (`/chat`), **Orchestrator** (mode-nudge classifier). Shared: `retriever.py`, `mode_detector.py`, `query_condenser.py`, `evangelho.py`, `stream_buffer.py`, `json_stream.py`, `conversation_log.py`, `crisis.py` (the last two, see Rules below).
- **`src/api/`** — FastAPI routes (`routes.py`), pydantic schemas (`schemas.py`). Stateless as a *service*: clients own the conversation history, `/chat` accepts it and no server-side session or database backs a request. That is not the same as "nothing is recorded" — every answered turn emits one JSON line to stdout for quality review (see the logging rule below), and the history itself is never among what it writes.

## Rules (these steer behavior — do not violate)

- **Grounding & attribution:** never invent doctrine; answer only from retrieved passages; keep source text visibly separate from AI explanation. Historical/cultural background from general knowledge is allowed *only* when the prose makes the distinction legible ("Historicamente… O texto, por sua vez…").
- **A fabricated quotation costs the whole answer, not the sentence.** `find_unsupported_quotes` (`quote_check.py`) runs **last, on the finished text**, on both `/chat` and `/study`; on a hit `/chat` returns `NOT_FOUND_MESSAGE` with no sources and `/study` returns an empty `contexto` with `generation_failed`. Either way nothing the model wrote is shown. The whole answer goes because the improvisation that invented a quotation wrote the paragraphs around it too. Two ordering rules were each paid for with a bug: it runs on what the **model** produced (never on text code inserted), and **after** markers are stripped (comparing a marker against the corpus can only fail).
- **Inline grounding markers are two vocabularies, and code owns the reference.** `/chat` marks the passage index its prompt printed (`[fonte N]`); `/study` marks the chapter item a reader can look up (`[item N]`) — the numbering differs because `/chat` retrieves across books, where a bare item number is ambiguous. `inline_refs.py` parses them out into positions on the clean text: **a marker naming something that was not retrieved is dropped, and no marker may reach the screen**. The model marks *where* a reference goes; code resolves *what* it names; the client renders it as a clickable link at that position. Never ask the model for the reference text — measured 2026-07-28, it does not produce it reliably.
- **Premise check is log-only, on purpose.** `unsupported_terms` (`premise_check.py`) flags a question built on a term the works never use, and the finding shapes the prompt — it never withholds an answer. This project shipped a guard tuned by reasoning instead of evidence twice, and **both times it withheld correct answers**; the numbers get looked at before any gate is added.
- **Never personify "o Espiritismo"** as an agent that does/values things — attribute doctrinal claims to the passage, the text, or Kardec. Applies to Explicador, Generator, and Reflexivo (currently switched off).
- **Crisis handling is a shared layer and does not live or die with any single mode.** `src/rag/crisis.py` is its own module precisely so that switching a mode off can never switch this off with it — Reflexivo is off today and the floor is untouched. It is **deterministic, never left to the LLM**: first-person ideation short-circuits to a fixed exit (CVV 188 / SAMU 192) **in code, before any retrieval or model call** — no doctrinal answer, no citations, no chips. A **topic-level** mention is not an exit: the question is answered from the works and the CVV note is appended **in code, always**. Above that floor, the `normal | abalo | crise` tier (`sensitivity.py`) can only ever **escalate** handling, never lower it. Constants, the filtering rules and the flow diagram: [architecture.md](docs/architecture.md#safety-the-deterministic-floor) — read it before changing anything here.
- **The crisis exit never streams.** It is fixed text decided in code before any model call, and arrives whole and immediate — a crisis message appearing letter by letter would be cruel and pointless. Small talk, the size cap and the rate limit likewise all answer before a stream is ever opened.
- **⚠️ Reflexivo is currently switched off** (see the modes table above) — the rest of this bullet describes it as it behaves when reconnected, not current production behavior: hard no-advice constraint (no suggestions, no course of action unless directly asked); the medical/mediumship caveat text (`_CAVEAT_INSTRUCTION` in `reflect_prompt.py`) is triggered by `needs_medical_caveat()` from `crisis.py`; after `CAP_ROUNDS` (5) rounds it forces a closing; 1–3 reflection questions per turn (fewer, sharper).
- **`/chat` trailer markers:** the model ends its answer with machine-readable `[FONTES: 1, 3]` (passages actually used; empty = no sources) and `[SEGUIR: q1 | q2]` (two follow-up chips). `strip_trailing_markers` in `markers.py` removes them (tolerant of malformed/`/FONTES:` variants). The answer text must **never end with a question** — follow-ups live only in `[SEGUIR]`.
- **No streamed token may ever contain `FONTES` or `SEGUIR`.** `stream_buffer.py` holds back any text that could still grow into a trailer marker, and the `done` event carries the fully post-processed answer — it is the source of truth, so a streamed response ends up identical to what `POST /chat` returns.
- **No streamed `/study` token may ever contain JSON syntax.** Explicador stays pinned to the JSON lane, so `json_stream.py` reads the `contexto` field out of the response as it arrives and holds back anything that could still be an incomplete escape — half a `\uXXXX` must never reach the screen as literal text. Same contract as `/chat`: `done` is parsed from the accumulated JSON with the same `_parse` the non-streaming lane uses, so a streamed `/study` is identical to `POST /study`. The `source` event comes before any token so the passage is on screen before the explanation of it.
- **Turn logging runs in two regimes, and the default one may never gain a link.** `src/rag/conversation_log.py` writes one JSON line per answered turn to stdout, which Cloud Logging captures and a sink forwards to BigQuery. Called from the route, never from a pipeline — the pipeline must not know observability exists. **Without consent** the record is what 2026-07-27 decided: loose turns, no `session_id`, nothing that could rebuild one person's thread. **With consent** — which travels *only* as the presence of the `X-Session-Id` header, so its absence IS the refusal — turns of one tab are linked. The backend **never generates a session id and never derives one** from IP, cookie or user-agent; `session_id` is absent from the object, not null, when it did not arrive. The conversation history is never logged, only `n_history`. **`crise` and `abalo` record no text at all, in either regime** — consent does not unlock them, because someone who clicked a banner on arrival did not meaningfully consent to what they would write in distress twenty minutes later. `retrieved` carries every chunk that reached the prompt (with raw `distance`, smaller is closer) while `sources` carries only what was cited: the gap between the two is the diagnosis. Every function here swallows its exceptions — observability may never break an answer that already worked. Reasoning: [the design](docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md), succeeding [the anonymous log](docs/superpowers/specs/2026-07-27-log-de-conversas-design.md), which still governs the default regime.
- **Privacy copy may promise less than the code does, never more.** `PRIVACY_NOTICE` in `frontend/src/constants/contact.js` deliberately omits the scrubbing of e-mail/phone/CPF/CEP and the no-text rule for `crise`/`abalo`. Tightening what the code does needs no edit there; **loosening it does** — check that text first.
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
