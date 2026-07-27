import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from fastapi import APIRouter, HTTPException

from src.api.paths import load_all_paths, load_path
from src.core.config import settings
from src.rag.evangelho import get_daily_passage
from src.rag.explicador import explicar as study_item_fn
from src.rag.generator import generate
from src.rag.mode_detector import extract_study_reference
from src.rag.orchestrator import classify_intent

# ReflectRequest and ReflectResponse are commented out below: Refletir is
# switched off, see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
from src.api.schemas import (  # isort: skip
    ChatRequest,
    ChatResponse,
    EvangelhoResponse,
    EvangelhoSource,
    PathDetail,
    PathSummary,
    # ReflectRequest,
    # ReflectResponse,
    Source,
    StudyRequest,
    StudyResponse,
)

# from src.rag.reflect import reflect as reflect_fn  # Refletir is switched off; see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md

router = APIRouter()

logger = logging.getLogger(__name__)

# Cap how long a response waits on the intent classifier. The answer runs on the
# calling thread; if the classifier is slower, we drop the nudge rather than
# delay the whole response.
_CLASSIFY_TIMEOUT_S = 8.0


def _answer_with_nudge(
    message: str,
    current_mode: str | None,
    history: list[dict],
    answer_fn: Callable[[], dict],
) -> tuple[dict, str | None]:
    """Run answer_fn on the calling thread while classify_intent runs in a
    worker thread; return (answer_result, suggested_mode). A slow or failing
    classifier degrades to no nudge instead of delaying or breaking the response.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        intent_future = executor.submit(classify_intent, message, current_mode, history)
        result = answer_fn()
        try:
            suggested_mode = intent_future.result(timeout=_CLASSIFY_TIMEOUT_S)["mode"]
        except Exception:
            logger.exception("classify_intent slow or failed; proceeding with no nudge")
            suggested_mode = None
    finally:
        # Don't join a stuck classifier thread; let it finish in the background.
        executor.shutdown(wait=False)
    return result, suggested_mode


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in request.history]
    result, suggested_mode = _answer_with_nudge(
        request.question,
        "tirar_duvida",
        history,
        lambda: generate(
            request.question,
            history,
            book_filter=request.book_filter,
            anchor_text=request.anchor_text,
        ),
    )
    if result.get("safety_level") == "crise":
        suggested_mode = None
    study_ref = (
        extract_study_reference(request.question)
        if suggested_mode == "estudar_obra"
        else {"item_number": None, "book": None}
    )
    return ChatResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        suggested_questions=result.get("suggested_questions", []),
        not_found=result["not_found"],
        suggested_mode=suggested_mode,
        suggested_item_number=study_ref["item_number"],
        suggested_book=study_ref["book"],
        generation_failed=result.get("generation_failed", False),
        safety_level=result.get("safety_level"),
    )


@router.get("/paths", response_model=list[PathSummary])
def list_paths() -> list[PathSummary]:
    paths = load_all_paths(settings.paths_dir)
    return [PathSummary(**p) for p in paths]


@router.get("/paths/{path_id}", response_model=PathDetail)
def get_path(path_id: str) -> PathDetail:
    path = load_path(settings.paths_dir, path_id)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "path_not_found", "path_id": path_id},
        )
    return PathDetail(**path)


@router.post("/study", response_model=StudyResponse)
def study(request: StudyRequest) -> StudyResponse:
    result = study_item_fn(request.book, request.item_number, request.chapter)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "item_not_found", "item_number": request.item_number},
        )
    return StudyResponse(**result)


# Refletir is switched off for production: the mode answers lived suffering with
# passages about reincarnation, and the 2026-07-26 retrieval evaluation showed no
# embedding model fixes it — the failure is structural, not a model choice. The
# code below is disconnected, not deleted; re-enabling is reconnecting it.
# See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
# @router.post("/reflect", response_model=ReflectResponse)
# def reflect_situation(request: ReflectRequest) -> ReflectResponse:
#     history = [m.model_dump() for m in request.conversation_history]
#     result, suggested_mode = _answer_with_nudge(
#         request.situation,
#         "refletir",
#         history,
#         lambda: reflect_fn(request.situation, history, anchor_text=request.anchor_text),
#     )
#     if result.get("safety_level") == "crise":
#         suggested_mode = None
#     study_ref = (
#         extract_study_reference(request.situation)
#         if suggested_mode == "estudar_obra"
#         else {"item_number": None, "book": None}
#     )
#     return ReflectResponse(
#         **result,
#         suggested_mode=suggested_mode,
#         suggested_item_number=study_ref["item_number"],
#         suggested_book=study_ref["book"],
#     )


@router.get("/evangelho", response_model=EvangelhoResponse)
def evangelho() -> EvangelhoResponse:
    passage = get_daily_passage()
    if passage is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "evangelho_not_indexed"},
        )
    return EvangelhoResponse(
        date=passage["date"],
        content=passage["content"],
        source=EvangelhoSource(**passage["source"]),
        chapter_summary=passage.get("chapter_summary"),
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
