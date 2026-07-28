import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.limits import (
    RATE_LIMITED_MESSAGE,
    TOO_LONG_MESSAGE,
    check_rate_limit,
    client_ip,
    exceeds_size_limit,
)
from src.api.paths import load_all_paths, load_path
from src.core.config import settings
from src.rag.conversation_log import log_chat_turn
from src.rag.crisis import needs_crisis_note
from src.rag.evangelho import get_daily_passage
from src.rag.explicador import build_sources
from src.rag.explicador import explicar as study_item_fn
from src.rag.explicador import explicar_stream, prepare_study
from src.rag.generator import generate, generate_stream
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


def _enforce_rate_limit(http_request: Request) -> None:
    retry_after = check_rate_limit(client_ip(http_request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "message": RATE_LIMITED_MESSAGE},
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    _enforce_rate_limit(http_request)
    started = time.monotonic()
    history = [m.model_dump() for m in request.history]

    # Crisis outranks the size cap, always. Someone writing at length about
    # wanting to die must get the CVV number, never "your message is too long"
    # — the guard that saves money can never be the one that answers that.
    if not needs_crisis_note(request.question) and exceeds_size_limit(
        request.question, history
    ):
        return _too_long_response()

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
    return _chat_response(
        request.question, result, suggested_mode, started_at=started, log=True
    )


@router.post("/chat/stream")
def chat_stream(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """Same answer as POST /chat, delivered as Server-Sent Events.

    POST /chat is unchanged and remains the recovery path: a client whose
    connection drops mid-stream can re-ask there rather than keep half a
    response. See docs/superpowers/specs/2026-07-27-streaming-design.md
    """
    _enforce_rate_limit(http_request)
    started = time.monotonic()
    history = [m.model_dump() for m in request.history]

    # Same ordering as POST /chat: crisis outranks the size cap, and the cap
    # answers before any stream is opened.
    if not needs_crisis_note(request.question) and exceeds_size_limit(
        request.question, history
    ):
        return _sse_response(_only_done(_too_long_response()))

    def events():
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            intent_future = executor.submit(
                classify_intent, request.question, "tirar_duvida", history
            )
            result: dict = {}
            for kind, payload in generate_stream(
                request.question,
                history,
                book_filter=request.book_filter,
                anchor_text=request.anchor_text,
            ):
                if kind == "token":
                    yield _sse("token", {"text": payload})
                else:
                    result = payload

            try:
                suggested_mode = intent_future.result(timeout=_CLASSIFY_TIMEOUT_S)[
                    "mode"
                ]
            except Exception:
                logger.exception(
                    "classify_intent slow or failed; proceeding with no nudge"
                )
                suggested_mode = None
        finally:
            # Don't join a stuck classifier thread; let it finish in the background.
            executor.shutdown(wait=False)

        response = _chat_response(
            request.question, result, suggested_mode, started_at=started, log=True
        )
        yield _sse("done", response.model_dump())

    return _sse_response(events())


def _chat_response(
    question: str,
    result: dict,
    suggested_mode: str | None,
    started_at: float,
    log: bool,
) -> ChatResponse:
    """Builds the /chat body. Shared with the stream's `done` event so the two
    routes cannot drift apart."""
    if result.get("safety_level") == "crise":
        suggested_mode = None
    study_ref = (
        extract_study_reference(question)
        if suggested_mode == "estudar_obra"
        else {"item_number": None, "book": None}
    )
    if log:
        log_chat_turn(
            question,
            result,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            suggested_mode=suggested_mode,
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


def _too_long_response() -> ChatResponse:
    return ChatResponse(
        answer=TOO_LONG_MESSAGE,
        sources=[],
        suggested_questions=[],
        not_found=False,
        suggested_mode=None,
        suggested_item_number=None,
        suggested_book=None,
        generation_failed=False,
        safety_level="normal",
    )


def _sse(event: str, data: dict) -> str:
    # ensure_ascii=False keeps the accented Portuguese readable on the wire;
    # the payload is JSON on one line, as the SSE framing requires.
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _only_done(response: ChatResponse):
    yield _sse("done", response.model_dump())


def _sse_response(events) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            # Nginx and the proxies derived from it honor this header and stop
            # accumulating the body before passing it on.
            "X-Accel-Buffering": "no",
        },
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
        raise _item_not_found(request.item_number)
    return StudyResponse(**result)


@router.post("/study/stream")
def study_stream(request: StudyRequest) -> StreamingResponse:
    """Same answer as POST /study, delivered as Server-Sent Events.

    POST /study is unchanged and remains the recovery path. The daily passage
    comes through here too: `handleStudyTrecho` studies the item when it is
    numbered, which is the normal case.
    See docs/superpowers/specs/2026-07-28-study-trecho-streaming-design.md
    """
    # Prepared before the stream opens so a missing item is still an HTTP 404.
    # Once the response starts streaming the status code is already sent, and a
    # not-found would have to masquerade as a successful empty answer.
    ctx = prepare_study(request.book, request.item_number, request.chapter)
    if ctx is None:
        raise _item_not_found(request.item_number)

    def events():
        # The passage first. It is known from retrieval, so the reader has the
        # text in front of them before the explanation of it starts arriving —
        # the order in which one reads. Waiting for `done` would put the
        # explanation on screen above the passage it explains.
        yield _sse(
            "source",
            {"original_text": ctx["original_text"], "sources": build_sources(ctx)},
        )
        for kind, payload in explicar_stream(ctx):
            if kind == "token":
                yield _sse("token", {"text": payload})
            else:
                yield _sse("done", StudyResponse(**payload).model_dump())

    return _sse_response(events())


def _item_not_found(item_number: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "item_not_found", "item_number": item_number},
    )


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
