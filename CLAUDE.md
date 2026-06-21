# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Kardec Study Assistant** is the backend of the *Dialoguing with the Doctrine* project — a RAG (Retrieval-Augmented Generation) system that answers questions grounded exclusively in Allan Kardec's five foundational Spiritist works. Responses must be strictly retrieval-grounded; hallucinated doctrine is unacceptable.

## Environment

- Package manager: **uv** (`uv sync --group dev` to set up)
- Python 3.12+
- Requires a `.env` file with `LLM_API_KEY` (OpenAI-compatible key)

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run the parsing pipeline (MD → JSON)
uv run python -m src.parsing.parsing_pipeline

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

This is the only fully implemented module. The pipeline is:

1. `cleaner.py` — strips LlamaCloud artifacts: page-number headers (`# 13`), `---` separators, hyphenated line breaks
2. `parser.py` — parses cleaned Markdown into structured chunks with metadata fields: `book`, `part`, `chapter`, `chapter_title`, `item_number`, `subchunk_index`, `total_subchunks`, `content`, `footnotes`
3. `chunking.py` — splits long item content into ≤2000-char subchunks at paragraph boundaries
4. `parsing_pipeline.py` — orchestrates all five books; maps filenames to canonical book names via `BOOK_NAME_MAP`

**Numbered items** (`123. - text`) are the primary structural unit in Livro dos Espíritos and Livro dos Médiuns. Books without numbered items (Evangelho, Gênese, Céu e Inferno) use `section-N` as the item identifier.

The Markdown source files (`data/markdown_files/`) are hand-reviewed and corrected — treat them as authoritative. Do not regenerate them from PDFs.

### Ingestion, RAG, and API Layers

`src/ingestion/`, `src/rag/`, and `src/api/` are scaffolded but empty. These are the next development targets. The README describes the intended responsibilities of each.

## Data

- `data/books/` — original PDFs (gitignored)
- `data/markdown_files/` — hand-reviewed Markdown source (committed, do not overwrite)
- `data/json_files/` — output of `pdm run parsing` (regenerable)
- `data/embeddings/` — vector DB (gitignored, regenerable)
