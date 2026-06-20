from fastapi import APIRouter

from src.api.schemas import ChatRequest, ChatResponse, Source
from src.rag.generator import generate

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = [m.model_dump() for m in request.history]
    result = generate(request.question, history)
    return ChatResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        not_found=result["not_found"],
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
