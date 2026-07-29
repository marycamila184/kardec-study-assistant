from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.config import settings

app = FastAPI(title="Dialogando com a Doutrina")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    # X-Session-Id carries the reader's consent. Without it listed here the
    # browser's preflight rejects every consented request — and a TestClient
    # never issues a preflight, so no route test can catch that.
    allow_headers=["Content-Type", "X-Session-Id"],
)

app.include_router(router)
