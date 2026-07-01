from openai import OpenAI

from src.core.config import settings
from src.rag.retriever import retrieve, retrieve_by_item
from src.rag.explicador_prompt import build_explicador_messages, parse_explicador_json
from src.rag.curador import curar

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def explicar(book: str, item_number: str, chapter: str | None = None) -> dict | None:
    chunks = retrieve_by_item(book, item_number, chapter)
    if not chunks:
        return None

    original_text = "\n\n".join(c["content"] for c in chunks)
    footnote_context = "\n\n".join(
        c["footnote_context"] for c in chunks if c.get("footnote_context")
    )

    all_related = retrieve(original_text, top_k=6)
    related = [
        r
        for r in all_related
        if not (
            r["metadata"]["item_number"] == item_number
            and r["metadata"]["book"] == book
        )
    ][:3]

    system, messages = build_explicador_messages(
        original_text, related, footnote_context=footnote_context
    )

    contexto = ""
    conceitos_chave: list[str] = []
    perguntas: list[str] = []
    generation_failed = False
    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        contexto, conceitos_chave, perguntas = parse_explicador_json(
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

    related_items = curar(original_text, related)

    return {
        "original_text": original_text,
        "contexto": contexto,
        "conceitos_chave": conceitos_chave,
        "perguntas": perguntas,
        "related_items": related_items,
        "sources": sources,
        "generation_failed": generation_failed,
    }
