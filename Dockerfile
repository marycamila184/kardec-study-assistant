# Runtime image for the FastAPI backend.
#
# The one thing this file exists to guarantee: torch never gets installed.
# `sentence-transformers` (and with it torch, CUDA and triton — ~4.7 GB) lives
# in the `ingest` dependency group, which runs offline on a developer machine.
# Production calls the same BAAI/bge-m3 over HTTP via EMBEDDING_PROVIDER, so
# `uv sync --no-dev` below is what keeps the image around 300 MB instead of 5 GB.
# On Cloud Run the image is pulled on every cold start, so that difference is
# paid in seconds of user-visible latency, not just in disk.

FROM python:3.12-slim

# uv resolves and installs from the lockfile; copying the binary from the
# official image avoids a pip bootstrap and pins the version.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies before source: the layer survives every code change, so a
# redeploy that only touches src/ does not reinstall anything.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ ./src/

# Only what the request path actually reads. data/json_files is ingestion input
# and data/books holds the PDFs — neither belongs in a running container.
#   data/embeddings/          the index that answers
#   data/paths/               curated learning paths, served by /paths
#   data/markdown_files/      trecho_diario.md, read by /evangelho
COPY data/embeddings/ ./data/embeddings/
COPY data/paths/ ./data/paths/
COPY data/markdown_files/trecho_diario.md ./data/markdown_files/trecho_diario.md

# Cloud Run injects PORT and it is not always 8080; binding a fixed port is the
# classic way to get a container that passes locally and fails to start there.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uv run --no-dev uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
