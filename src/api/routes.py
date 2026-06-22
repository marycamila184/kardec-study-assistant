from fastapi import APIRouter, HTTPException

from src.api.paths import load_all_paths, load_path
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    EvangelhoResponse,
    EvangelhoSource,
    PathDetail,
    PathSummary,
    ReflectRequest,
    ReflectResponse,
    Source,
    StudyRequest,
    StudyResponse,
)
from src.core.config import settings
from src.rag.evangelho import get_daily_passage
from src.rag.generator import generate
from src.rag.mode_detector import detect_suggested_mode
from src.rag.reflect import reflect as reflect_fn
from src.rag.study import study as study_item_fn

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in request.history]
    result = generate(request.question, history)
    suggested_mode = detect_suggested_mode(request.question)
    return ChatResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        not_found=result["not_found"],
        suggested_mode=suggested_mode,
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
    result = study_item_fn(request.book, request.item_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "item_not_found", "item_number": request.item_number},
        )
    return StudyResponse(**result)


@router.post("/reflect", response_model=ReflectResponse)
def reflect_situation(request: ReflectRequest) -> ReflectResponse:
    result = reflect_fn(request.situation)
    return ReflectResponse(**result)


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
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
