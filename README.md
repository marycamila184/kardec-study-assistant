# Kardec Study Assistant — Dialogando com a Doutrina

**Dialogando com a Doutrina** is a study companion for Allan Kardec's Spiritist works. It uses Retrieval-Augmented Generation (RAG) to deliver grounded, accessible answers strictly based on the original texts — never hallucinated doctrine.

The project is split into two independent apps that are deployed separately:

| App | Folder | Purpose |
|-----|--------|---------|
| **Backend** | `/` (root) | FastAPI RAG API — parsing, ingestion, retrieval, LLM generation |
| **Frontend** | `frontend/` | React + Vite web interface |

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

The app will be available at `http://localhost:5173`.

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

The frontend is a static site after `npm run build`. Deploy to any static hosting provider (Netlify, Vercel, GitHub Pages, Cloudflare Pages, etc.):

1. Build: `npm run build` (run from the `frontend/` folder)
2. Publish directory: `frontend/dist`
3. Set the backend API URL as an environment variable so the frontend knows where to send requests (exact variable name depends on how the frontend is configured).

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
├── frontend/                   # React + Vite frontend app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── constants/          # Theme, books, learning paths
│   │   ├── hooks/              # useTheme, useFavorites, useConversations, etc.
│   │   └── styles/
│   ├── index.html
│   ├── vite.config.js
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
- Conversation memory support (server-side; currently client-owned)
- Multilingual support
- Deployment infrastructure

---

## Other Commands

```bash
# Format and lint (backend)
uv run black src/
uv run isort src/

# Run tests (backend)
uv run pytest
uv run pytest tests/path/to/test_file.py::TestClass::test_name
```

---

## License

All doctrinal texts used in this project are in the public domain.

The software architecture is open for extension and research purposes.
