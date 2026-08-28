import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from src.api.limits import (
    RATE_LIMITED_MESSAGE,
    TOO_LONG_MESSAGE,
    check_rate_limit,
    client_ip,
    exceeds_size_limit,
    trim_history,
)
from src.api.paths import load_all_paths, load_path
from src.core.config import settings
from src.push import store as push_store
from src.rag.conversation_log import log_chat_turn, log_feedback, log_study_turn
from src.rag.crisis import needs_crisis_note
from src.rag.evangelho import get_daily_passage
from src.rag.explicador import build_sources
from src.rag.explicador import explicar as study_item_fn
from src.rag.explicador import explicar_stream, prepare_study
from src.rag.generator import generate, generate_stream
from src.rag.mode_detector import extract_study_reference
from src.rag.orchestrator import classify_intent
from src.rag.profile import CHAT_DEFAULT, MODE_DEFAULTS, ResponseProfile
from src.rag.profile_detector import detect_profile_changes

# ReflectRequest and ReflectResponse are commented out below: Refletir is
# switched off, see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
from src.api.schemas import (  # isort: skip
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    ProfileState,
    EvangelhoResponse,
    EvangelhoSource,
    PathDetail,
    PathSummary,
    PushEndpointRequest,
    PushSubscribeRequest,
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


# The shape classifier shapes the prompt, so unlike classify_intent it cannot
# overlap generation — the prompt is built from it. But it does not need
# retrieval, and retrieval does not need it, so it overlaps THAT instead: the
# route starts it and hands the generator a resolver, which is read at the last
# moment, just before the prompt is built.
#
# The budget is a deadline rather than a wait, and that is the whole point. It
# is measured from the moment detection STARTS, so whatever condensation,
# embedding and retrieval consumed is time the classifier already had. On the
# common path it is finished long before anyone asks, and the added latency is
# zero. It used to be 3s of serial prelude on every turn, and production was
# logging its TimeoutError — readers paid the full 3s and got the unchanged
# profile anyway.
_PROFILE_TIMEOUT_S = 3.0


def _profile_resolver(
    question: str, state: ProfileState | None, current_mode: str | None = None
) -> Callable[[], ResponseProfile]:
    """Starts profile detection and returns the way to read it.

    The profile for this turn is what the client carried in, plus anything this
    message asks to change. With nothing carried in, the mode decides the
    starting point — a first question in Estudar is not the same as a first
    question in Dialogar.

    The result is memoised: the generator reads it to build the prompt and the
    route reads it again to report it on the response, and those two must be the
    same profile, resolved once.
    """
    incoming = MODE_DEFAULTS.get(current_mode or "", CHAT_DEFAULT)
    if state is not None:
        incoming = ResponseProfile(
            citation_style=state.citation_style,
            citation_precision=state.citation_precision,
            depth=state.depth,
            vocabulary=state.vocabulary,
            sections=CHAT_DEFAULT.sections,
            pinned=frozenset(state.pinned),
        )

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(detect_profile_changes, question, incoming)
    deadline = time.monotonic() + _PROFILE_TIMEOUT_S
    resolved: list[ResponseProfile] = []

    def resolve() -> ResponseProfile:
        if resolved:
            return resolved[0]
        try:
            profile = future.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:
            logger.exception("profile detection slow or failed; profile unchanged")
            profile = incoming
        finally:
            executor.shutdown(wait=False)
        resolved.append(profile)
        return profile

    return resolve


def _profile_state(profile: ResponseProfile) -> ProfileState:
    return ProfileState(
        citation_style=profile.citation_style,
        citation_precision=profile.citation_precision,
        depth=profile.depth,
        vocabulary=profile.vocabulary,
        pinned=sorted(profile.pinned),
    )


def _enforce_rate_limit(http_request: Request) -> None:
    retry_after = check_rate_limit(client_ip(http_request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "message": RATE_LIMITED_MESSAGE},
            headers={"Retry-After": str(retry_after)},
        )


def session_id_from(http_request: Request) -> str | None:
    """The reader's consent, as the presence of a header.

    Absence IS the refusal — there is no boolean flag that could be sent as
    true by mistake, and no request schema had to change. The backend never
    generates this and never falls back to IP, cookie or user-agent: if the
    header did not arrive, there is no session, so a frontend bug errs safe.
    The `or None` collapses a header that arrived blank into refusal too.

    See docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
    """
    return http_request.headers.get("X-Session-Id") or None


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    _enforce_rate_limit(http_request)
    started = time.monotonic()
    history = [m.model_dump() for m in request.history]

    # Crisis outranks the size cap, always. Someone writing at length about
    # wanting to die must get the CVV number, never "your message is too long"
    # — the guard that saves money can never be the one that answers that.
    if not needs_crisis_note(request.question) and exceeds_size_limit(request.question):
        return _too_long_response()

    # A long conversation is trimmed, not refused. Only a single over-long
    # message is turned away.
    history = trim_history(request.question, history)

    profile = _profile_resolver(request.question, request.profile, request.current_mode)
    result, suggested_mode = _answer_with_nudge(
        request.question,
        # The mode the CLIENT reports, never a constant: classify_intent's
        # self-suppression compares against this, so hardcoding it told the
        # orchestrator every reader was in Dialogar and let it nudge someone
        # inside Estudar toward Estudar. `scripts/check_chat_current_mode.mjs`
        # cannot see this — it only guards the frontend call sites.
        request.current_mode,
        history,
        lambda: generate(
            request.question,
            history,
            book_filter=request.book_filter,
            chapter_filter=request.chapter_filter,
            anchor_text=request.anchor_text,
            profile=profile,
        ),
    )
    return _chat_response(
        request.question,
        result,
        suggested_mode,
        started_at=started,
        log=True,
        # Already resolved by the generator; memoised, so this is a read.
        profile=profile(),
        session_id=session_id_from(http_request),
        n_history=len(history),
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
    if not needs_crisis_note(request.question) and exceeds_size_limit(request.question):
        return _sse_response(_only_done(_too_long_response()))

    history = trim_history(request.question, history)

    profile = _profile_resolver(request.question, request.profile, request.current_mode)
    # Read before the stream opens: inside the generator the request may already
    # be gone by the time the body starts being consumed.
    session_id = session_id_from(http_request)
    n_history = len(history)

    def events():
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            # Same contract as POST /chat: the client's mode, not a constant.
            intent_future = executor.submit(
                classify_intent, request.question, request.current_mode, history
            )
            result: dict = {}
            for kind, payload in generate_stream(
                request.question,
                history,
                book_filter=request.book_filter,
                chapter_filter=request.chapter_filter,
                anchor_text=request.anchor_text,
                profile=profile,
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
            request.question,
            result,
            suggested_mode,
            started_at=started,
            log=True,
            # Already resolved by the generator; memoised, so this is a read.
            profile=profile(),
            session_id=session_id,
            n_history=n_history,
        )
        yield _sse("done", response.model_dump())

    return _sse_response(events())


def _chat_response(
    question: str,
    result: dict,
    suggested_mode: str | None,
    started_at: float,
    log: bool,
    profile: ResponseProfile | None = None,
    session_id: str | None = None,
    n_history: int = 0,
    mode: str = "chat",
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
    turn_id = None
    if log:
        turn_id = log_chat_turn(
            question,
            result,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            suggested_mode=suggested_mode,
            session_id=session_id,
            mode=mode,
            n_history=n_history,
        )
    return ChatResponse(
        answer=result["answer"],
        turn_id=turn_id,
        studied_item=result.get("studied_item"),
        profile=_profile_state(profile) if profile else None,
        inline_refs=result.get("inline_refs", []),
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


@router.post("/feedback", status_code=204)
def feedback(request: FeedbackRequest, http_request: Request) -> Response:
    """A vote on an answer.

    Works with or without consent: {turn_id, vote} describes no person and
    links no turns, so refusing the banner does not take away someone's ability
    to say the answer was bad.

    No rate limit: a vote is one log line, and the cost of abusing that is
    negligible next to the cost of turning away an honest reader.
    """
    log_feedback(request.turn_id, request.vote, session_id_from(http_request))
    return Response(status_code=204)


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
def study(request: StudyRequest, http_request: Request) -> StudyResponse:
    # /study was missed when the abuse guards went in, and it is the more
    # expensive route: two model calls per request (Explicador and Curador),
    # public and unauthenticated.
    _enforce_rate_limit(http_request)
    started = time.monotonic()
    result = study_item_fn(
        request.book, request.item_number, request.chapter, request.part
    )
    if result is None:
        raise _item_not_found(request.item_number)
    return _study_response(
        request, result, started_at=started, session_id=session_id_from(http_request)
    )


@router.post("/study/stream")
def study_stream(request: StudyRequest, http_request: Request) -> StreamingResponse:
    """Same answer as POST /study, delivered as Server-Sent Events.

    POST /study is unchanged and remains the recovery path. The daily passage
    comes through here too: `handleStudyTrecho` studies the item when it is
    numbered, which is the normal case.
    See docs/superpowers/specs/2026-07-28-study-trecho-streaming-design.md
    """
    _enforce_rate_limit(http_request)

    # Prepared before the stream opens so a missing item is still an HTTP 404.
    # Once the response starts streaming the status code is already sent, and a
    # not-found would have to masquerade as a successful empty answer.
    started = time.monotonic()
    # Read before the stream opens, like /chat/stream: inside the generator the
    # request may already be gone.
    session_id = session_id_from(http_request)

    ctx = prepare_study(
        request.book, request.item_number, request.chapter, request.part
    )
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
                # Logged here, with the post-processed payload — the same
                # object POST /study logs, so both lanes produce one identical
                # line.
                response = _study_response(
                    request, payload, started_at=started, session_id=session_id
                )
                yield _sse("done", response.model_dump())

    return _sse_response(events())


def _study_response(
    request: StudyRequest,
    result: dict,
    started_at: float,
    session_id: str | None,
) -> StudyResponse:
    """Logs the studied turn and builds the body. Shared by POST /study and the
    stream's `done` event so the two cannot describe the same item differently
    — the same reason `_chat_response` exists.

    `result` carries a log-only `retrieved` key. StudyResponse is built from
    named fields, so pydantic drops it and it never reaches the client.
    """
    turn_id = log_study_turn(
        request.book,
        request.item_number,
        request.chapter,
        result,
        latency_ms=int((time.monotonic() - started_at) * 1000),
        session_id=session_id,
    )
    return StudyResponse(**{**result, "turn_id": turn_id})


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


# --- Lembrete por push ---
#
# Três rotas, todas 204 e sem corpo, e nenhuma delas escreve no log de
# turnos: o store das subscriptions não cruza com nada. Ver
# docs/superpowers/specs/2026-08-27-lembrete-push-design.md


@router.post("/push/subscribe", status_code=204)
def push_subscribe(request: PushSubscribeRequest) -> Response:
    push_store.save(
        push_store.Subscription(
            endpoint=request.endpoint,
            keys={"p256dh": request.keys.p256dh, "auth": request.keys.auth},
            hour=request.hour,
            timezone=request.timezone,
            last_seen=date.today(),
        )
    )
    return Response(status_code=204)


@router.post("/push/unsubscribe", status_code=204)
def push_unsubscribe(request: PushEndpointRequest) -> Response:
    push_store.delete(request.endpoint)
    return Response(status_code=204)


@router.post("/push/seen", status_code=204)
def push_seen(request: PushEndpointRequest) -> Response:
    """Carimba last_seen quando alguém abre o app por um lembrete.

    Só a data. É o que permite os 90 dias existirem — sem nada registrando
    atividade, a expiração nunca dispararia.
    """
    push_store.touch(request.endpoint, date.today())
    return Response(status_code=204)
