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
| Embeddings | SentenceTransformers (`paraphrase-multilingual-mpnet-base-v2`) |
| Vector store | ChromaDB |
| LLM provider | Groq (OpenAI-compatible endpoint) |
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
GROQ_API_KEY=your_groq_api_key_here
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
| `POST` | `/reflect` | Reflect on a personal situation (Refletir sobre uma Situação) |
| `GET` | `/evangelho` | Daily passage from O Evangelho segundo o Espiritismo |
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

The FastAPI app is a standard Python ASGI app. Deploy to any provider that supports Python (Render, Railway, Fly.io, etc.):

1. Set the `GROQ_API_KEY` environment variable on the provider.
2. The vector database (`data/embeddings/`) is regenerable — run the ingestion pipeline as part of your build/start process, or mount it as a persistent volume.
3. Start command: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

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
├── .env                        # Not committed — add your GROQ_API_KEY here
└── README.md
```

---

## Roadmap

- ✅ RAG pipeline (parsing, ingestion, retrieval, generation)
- ✅ All four study modes as API endpoints
- ✅ Curated learning paths
- ✅ Web interface (React + Vite frontend)
- Frontend → backend API integration (currently mocked)
- Conversation memory support
- Citation formatting improvements
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
