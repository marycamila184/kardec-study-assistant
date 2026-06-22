from openai import OpenAI

from src.core.config import settings
from src.rag.retriever import retrieve, retrieve_by_item
from src.rag.study_prompt import build_study_messages, parse_llm_json

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def study(book: str, item_number: str, chapter: str | None = None) -> dict | None:
    chunks = retrieve_by_item(book, item_number, chapter)
    if not chunks:
        return None

    original_text = "\n\n".join(c["content"] for c in chunks)

    all_related = retrieve(original_text, top_k=6)
    related = [
        r
        for r in all_related
        if not (
            r["metadata"]["item_number"] == item_number
            and r["metadata"]["book"] == book
        )
    ][:3]

    system, messages = build_study_messages(original_text, related)

    explanation = ""
    practical_example = ""
    generation_failed = False
    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        explanation, practical_example = parse_llm_json(
            response.choices[0].message.content
        )
    except Exception:
        generation_failed = True

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in chunks
    ]

    related_items = [
        {
            "book": r["metadata"]["book"],
            "item_number": r["metadata"]["item_number"],
            "preview": r["content"][:200],
        }
        for r in related
    ]

    return {
        "original_text": original_text,
        "explanation": explanation,
        "practical_example": practical_example,
        "related_items": related_items,
        "sources": sources,
        "generation_failed": generation_failed,
    }
