# Kardec Study Assistant — Dialogando com a Doutrina

**Dialogando com a Doutrina** is a study companion for Allan Kardec's Spiritist works. It uses Retrieval-Augmented Generation (RAG) to deliver grounded, accessible answers strictly based on the original texts — never hallucinated doctrine.

The project is split into two independent apps that are deployed separately:

| App | Folder | Purpose |
|-----|--------|---------|
| **Backend** | `/` (root) | FastAPI RAG API — parsing, ingestion, retrieval, LLM generation |
| **Frontend** | `frontend/` | React + Vite web interface |

**Status:** the backend is live on Cloud Run at
`https://kardec-api-391789792183.us-central1.run.app` (`us-central1`, scaling to
zero). Deployment commands and the two traps that cost a build each are in
[docs/deploy.md](docs/deploy.md).

In production the embedding lane is hosted (`EMBEDDING_PROVIDER`), so the image
carries no torch; locally the same `BAAI/bge-m3` runs in-process. The two were
measured equivalent on 2026-07-27 — cosine 0.999994, 100% top-5 overlap — which
is why one index serves both.

---

## Project Purpose

- Transform doctrinal texts into semantic embeddings
- Enable contextual retrieval of relevant excerpts
- Generate grounded responses using a Large Language Model (LLM)
- Serve answers via a clean REST API
- Maintain doctrinal traceability (book, part, chapter, item)

This is **not** a chatbot trained on Spiritism. It is a **retrieval-grounded system** that answers strictly based on the original texts.

---

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| API framework | FastAPI |
| Package manager | uv |
| Embeddings | `BAAI/bge-m3` — in-process locally, hosted in production (same model, see below) |
| Vector store | ChromaDB |
| LLM provider | Together (OpenAI-compatible endpoint) |
| PDF → Markdown | LlamaCloud (run once, output committed) |

### Frontend
| Layer | Technology |
|-------|-----------|
| Language | JavaScript (React 18) |
| Build tool | Vite 5 |
| Package manager | npm |

---

## Running the Backend

### 1. Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) installed
- A `.env` file in the project root with:

```
TOGETHER_API_KEY=your_together_api_key_here
```

### 2. Install dependencies

```bash
uv sync --group dev
```

### 3. Build the vector database (first time only)

```bash
# Parse Markdown files into structured JSON
uv run python -m src.parsing.parsing_pipeline

# Embed JSON chunks and index into ChromaDB
uv run python -m src.ingestion.pipeline
```

### 4. Start the API server

```bash
uv run fastapi dev src/api/main.py
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Available Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Ask a doctrinal question (Tirar uma Dúvida) |
| `POST` | `/study` | Study a specific item from a book (Estudar uma Obra) |
| `GET` | `/evangelho` | Daily passage from O Evangelho segundo o Espiritismo |
| ~~`POST`~~ | ~~`/reflect`~~ | **Switched off.** Retrieval eval showed Refletir answers lived suffering with reincarnation passages, unfixable by embedding-model swap. Route is commented out (404 by absence, not a deliberate 503); code is disconnected, not deleted. See `docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md`. The shared crisis layer (deterministic suicidal-ideation handling, CVV 188 / SAMU 192) does not depend on this mode — it lives in `src/rag/crisis.py` and stays fully active on `/chat`. |
| `GET` | `/paths` | List curated learning paths |
| `GET` | `/paths/{path_id}` | Full learning path detail |
| `GET` | `/health` | Health check |

---

## Running the Frontend

### 1. Prerequisites

- Node.js 18+ and npm installed

### 2. Install dependencies

```bash
cd frontend
npm install
```

### 3. Start the dev server

```bash
npm run dev
```

This runs `astro dev`. The app will be available at `http://localhost:4321`.

> **Note:** The frontend expects the backend API to be running. In development both should be running at the same time. In production they are deployed separately (see Deployment below).

### Other commands

```bash
npm run build    # build for production (outputs to frontend/dist/)
npm run preview  # preview the production build locally
```

---

## Deployment

The backend and frontend are deployed independently.

### Backend deployment

**Full command-by-command guide: [docs/deploy.md](docs/deploy.md).** Target is
Cloud Run (`us-central1`) with the frontend on Vercel; the reasoning behind
every choice is in
`docs/superpowers/specs/2026-07-27-deploy-cloud-run-vercel-design.md`.

The three things that shape the deployment:

**1. The image must not contain torch.** `sentence-transformers` pulls torch and
CUDA — about 4.7 GB that exists only to run `BAAI/bge-m3` in-process. It lives in
the `ingest` dependency group, so `uv sync --no-dev` (what the `Dockerfile` runs)
leaves it out and the image lands near 300 MB. On Cloud Run the image is pulled
on every cold start, so that weight would be paid in user-visible latency.

**2. Production calls the same embedding model over HTTP.** Set
`EMBEDDING_PROVIDER=openrouter` (or `deepinfra`/`novita`) plus the matching key.
It is the *same* `BAAI/bge-m3`: parity was measured on 2026-07-27 at cosine
0.999994 against the stored vectors, with 100% top-5 overlap, so the existing
index stays valid and no threshold needs recalibrating.

**3. The index ships inside the image.** The corpus is static and nothing is
written at runtime, so `data/embeddings/` is copied in — no volume, no bucket,
no download on cold start. The trade-off is deliberate: updating the corpus
means rebuilding the image.

Region is a US one on purpose. Every model call leaves Brazil regardless
(Together answered in 832ms and the hosted embedding in 346ms from São Paulo),
and `/chat` makes two remote calls in sequence — so the backend belongs next to
the providers, where the user pays one ocean crossing instead of two.

Environment on the service: `LLM_PROVIDER`, `EMBEDDING_PROVIDER` and
`CORS_ALLOWED_ORIGINS` as plain vars; API keys via Secret Manager, never
`--set-env-vars`.

If `PROSE_PROVIDER` is set, the backend also needs a reachable prose endpoint:
either a local Ollama (`ollama pull hf.co/ia-espirita/riv-ai-v2-Q4_K_M-GGUF`) or
a hosted OpenAI-compatible endpoint via `HF_ENDPOINT_URL`. Leaving
`PROSE_PROVIDER` unset requires no extra infrastructure.

### Frontend deployment

The frontend is a static site after `npm run build`. It targets **Vercel** (see
[docs/deploy.md](docs/deploy.md)); any static host works, but the API URL has to
reach the deployed backend either way:

1. Build: `npm run build` (run from the `frontend/` folder)
2. Publish directory: `frontend/dist`
3. Set the backend API URL as an environment variable so the frontend knows where to send requests (exact variable name depends on how the frontend is configured).
4. `frontend/public/` ships verbatim with the build — `preview.png`, `robots.txt`, `sitemap.xml` and the trilha pages need no configuration of their own. `/sobre/` is built from an Astro page, not `public/`, but needs none either.

Two manual steps after every deploy, neither of them a code change:

- Check the share card at `developers.facebook.com/tools/debug` **before** sending the link anywhere — WhatsApp caches previews aggressively, so a mistake found after the first share is expensive to correct.
- Register the site in Google Search Console and submit `https://dialogandodoutrina.com.br/sitemap.xml`.

---

## Data Source & Copyright

The five doctrinal works were collected from Brazil's public domain repository:

http://www.dominiopublico.gov.br/pesquisa/PesquisaObraForm.jsp

All books are publicly available and free of copyright restrictions. The Markdown source files in `data/markdown_files/` are hand-reviewed — do not regenerate them from PDFs.

---

## Project Structure

```
kardec-study-assistant/
│
├── frontend/                   # Astro frontend, with a React app mounted as an island
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/               # index.astro (mounts App as client:only), sobre.astro (no island, no script)
│   │   ├── layouts/             # Base.astro — shared <head>, meta tags
│   │   ├── content/             # frases.json — sentences shared by index.astro and sobre.astro
│   │   ├── constants/           # Theme, books, learning paths
│   │   ├── hooks/                # useTheme, useFavorites, useConversations, etc.
│   │   └── styles/
│   ├── public/                  # copied verbatim into dist/ by Astro, no bundling
│   │   ├── trilhas/<slug>/index.html  # generated by src/discovery/generate, served at /trilhas/<slug>/
│   │   ├── robots.txt          # allow all, points at sitemap.xml
│   │   ├── sitemap.xml         # lists /, /sobre/ and every trilha
│   │   └── preview.png         # 1200x630 social share card
│   ├── astro.config.mjs
│   └── package.json
│
├── data/
│   ├── books/                  # Original public-domain PDFs (gitignored)
│   ├── embeddings/             # ChromaDB vector store (gitignored, regenerable)
│   ├── markdown_files/         # Hand-reviewed Markdown source (committed)
│   ├── json_files/             # Parsed JSON chunks (regenerable)
│   └── paths/                  # Curated learning path JSON files (committed)
│
├── src/
│   ├── api/                    # FastAPI endpoints and schemas
│   ├── parsing/                # Markdown cleaning and structural parsing
│   ├── ingestion/              # Embedding + ChromaDB ingestion pipeline
│   └── rag/                    # Retrieval, prompting, and generation
│
├── tests/
├── pyproject.toml
├── .env                        # Not committed — add your TOGETHER_API_KEY here
└── README.md
```

---

## Roadmap

- ✅ RAG pipeline (parsing, ingestion, retrieval, generation)
- ✅ All four study modes as API endpoints — Refletir sobre uma Situação is currently switched off (see Available Endpoints above and `docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md`); the other three ship
- ✅ Curated learning paths
- ✅ Web interface (React + Vite frontend)
- ✅ Frontend → backend API integration
- ✅ Clickable source citations (excerpt modal) on `/chat` (also built for `/reflect`, currently switched off)
- ✅ Related-items modal with click-through to full study
- ✅ Deployment infrastructure — Cloud Run (backend) + Vercel (frontend), index baked into the image, hosted embedding lane
- **Refletir sobre uma Situação — in development, not shipped.** The mode exists in full (`src/rag/reflect.py`, `reflect_prompt.py`, `RefletirPicker.jsx`) and is disconnected rather than deleted, so re-enabling is wiring rather than rewriting. What keeps it off is measured: the 2026-07-26 retrieval evaluation found that all four embedding models tested answer *"estou me sentindo ansioso"* with the chapter on a Spirit's agony before **reincarnating**. The failure looked structural, so the fix was taken to be chapter-level filtering rather than a model swap. See `docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md` — **and note the 2026-07-29 measurement below, which weakens that conclusion**
- ✅ Measured 2026-07-29: **Qwen3-Embedding-8B evaluated against bge-m3, bge-m3 kept.** The verdict is split — Qwen wins the `reflexivo` set decisively (`avoid_hits` 6 → 1 at 4096 dims) and loses the `chat` set, which is the one in production. It also shows 4096 dims buy nothing over the MRL-truncated 1024, settling whether the native width is worth 4× the index on every cold start. Cost: US$0.026. The `avoid_hits` result is real evidence *against* "a model swap cannot fix Reflexivo", though with n=9 it argues for reopening the question, not for reconnecting the mode. Numbers in `docs/architecture.md`
- ✅ Fixed 2026-07-29: **`max_distance` lowered 0.55 → 0.45, from a measured gap.** Covered questions find their apt chapter between 0.319 and 0.379; questions the works do not address have their best passage between 0.474 and 0.546 — no overlap. At 0.55 nothing was stopped, so an uncovered question still reached the model with five weak passages, and that is what it improvised doctrine on top of. The test guards the gap, not the value
- Deterministic suppression of follow-up chips on sensitive turns — measured 2026-07-26: `gemini-3.6-flash` offered one right below the CVV note, and the current model's silence there is luck, not a guarantee
- ✅ Fixed 2026-07-29: the 20 documents that overwrote each other in the index — `_build_id` omitted `part`, so O Céu e o Inferno's two chapter I collided. The key now carries `part` when present, and ingestion stores all 7347. **Requires a rebuild from empty, not a re-ingestion:** ids change for the three books that have parts (Céu e Inferno, O Livro dos Espíritos, O Livro dos Médiuns), so re-ingesting over the old index leaves ~4451 orphan rows
- Conversation memory support (server-side; currently client-owned)
- Multilingual support

### Planned

**riv-ai-v2 for Refletir.** Whether a model fine-tuned on Spiritist material
holds the reflective register better than the general one. The obstacle is
already known and has to be re-measured rather than assumed: riv-ai-v2 was cut
from Reflexivo on 2026-07-24 for giving direct advice, which the mode forbids
outright — and that verdict came from an ad-hoc n=5 smoke test whose raw output
was never saved. `scripts/compare_reflect.py` exists to make that evidence
reproducible. Any return of the mode has to clear the no-advice constraint on
the record, not from memory.

**Spiritist centre map.** A directory of nearby centres, using the reader's
location. The open question is where it belongs: it is not a study mode, and
putting it beside Estudar/Dialogar would suggest it is one. Estudar is the
current candidate, since someone who has just read a passage is closer to
wanting a room with people in it than someone mid-question. Needs a data source
for the centres and an explicit, revocable location permission — the app asks
for nothing today, and that is worth keeping true until the feature earns it.

**A warmer, more capable conversational agent.** Today the reader asks and gets
an answer. The next step is a companion that can act on the works during the
conversation — open a chapter when the reader wants to go deeper, and bring the
passage along instead of describing it. The constraint that governs everything
else applies unchanged: whatever it opens must be shown as source text, visibly
separate from anything the model adds.

**Study module content review** A doctrinal pass over the curated
learning paths and the Explicador output. Retrieval quality is measured; whether
the *pedagogy* is sound is not something a benchmark answers.

**Prompt caching on Together.** Every `/chat` turn resends the system prompt and
the retrieved passages, and prompt tokens dominate the bill — this is where the
spend actually is. Worth measuring the hit rate before assuming the saving:
cache economics depend on how much of the prompt is genuinely stable across
turns, and the retrieved passages are the part that changes.

**Fine-tuning, later.** A model that reads as a teacher rather than an
encyclopaedia, trained on recorded teaching — podcasts and lectures. Two
prerequisites before any of it: rights to the material must be cleared with
whoever produced it, and the grounding rule has to survive. A fine-tune that
starts speaking doctrine from its weights instead of from retrieved passages
would break the one thing this project refuses to break.

---

## Other Commands

```bash
# Format and lint (backend)
uv run black src/
uv run isort src/

# Run tests (backend)
uv run pytest
uv run pytest tests/path/to/test_file.py::TestClass::test_name

# Frontend checks — there is no test runner in frontend/, so the pure
# functions are exercised as plain Node scripts
node scripts/check_cited_text.mjs          # citation splitting and labels
node scripts/check_followup_reply.mjs      # follow-ups drop the visible passage
node scripts/check_chat_current_mode.mjs   # every /chat call declares current_mode
node scripts/check_discovery_assets.mjs    # meta tags, preview.png, /sobre/, robots, sitemap

# Evaluation harnesses (cost money; read as comparisons between lanes)
uv run python -m scripts.compare_retrieval --report      # embedding models
uv run python -m scripts.compare_generators --report-only # prompts / models
```

---

## License

All doctrinal texts used in this project are in the public domain.

The software architecture is open for extension and research purposes.
