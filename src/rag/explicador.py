import concurrent.futures
import logging

from src.core.config import settings
from src.rag.curador import curar
from src.rag.explicador_prompt import build_explicador_messages, parse_explicador_json
from src.rag.llm_client import get_client
from src.rag.retriever import chapter_commentary, retrieve, retrieve_by_item

logger = logging.getLogger(__name__)


def explicar(book: str, item_number: str, chapter: str | None = None) -> dict | None:
    # Note: retrieve_by_item failures are left unhandled here (surface as a
    # 500), rather than mapped to the 404 "item not found" response — a DB
    # failure and a real not-found are different situations and shouldn't
    # look the same to the client.
    chunks = retrieve_by_item(book, item_number, chapter)
    if not chunks:
        return None

    original_text = "\n\n".join(c["content"] for c in chunks)
    footnote_context = "\n\n".join(
        c["footnote_context"] for c in chunks if c.get("footnote_context")
    )

    related_query = chunks[0]["content"]
    try:
        all_related = retrieve(related_query, top_k=6)
    except Exception:
        logger.exception("related-items retrieve failed in explicador")
        all_related = []
    related = [
        r
        for r in all_related
        if not (
            r["metadata"]["item_number"] == item_number
            and r["metadata"]["book"] == book
        )
    ][:3]

    commentary = chapter_commentary(book, chapter or "", item_number)

    system, messages = build_explicador_messages(
        original_text,
        related,
        footnote_context=footnote_context,
        chapter_commentary_chunks=commentary,
    )

    def _call_explicador():
        response = get_client().chat.completions.create(
            model=settings.resolved_chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return parse_explicador_json(response.choices[0].message.content)

    contexto = ""
    conceitos_chave: list[str] = []
    perguntas: list[str] = []
    generation_failed = False

    # curar() makes its own independent Groq call and only needs `related`,
    # which is already available — run both LLM calls concurrently instead
    # of paying their latency twice in sequence.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        explicador_future = executor.submit(_call_explicador)
        curador_future = executor.submit(curar, original_text, related)

        try:
            contexto, conceitos_chave, perguntas = explicador_future.result()
        except Exception:
            logger.exception("explicador LLM call/parse failed")
            generation_failed = True

        related_items = curador_future.result()

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in chunks
    ]

    return {
        "original_text": original_text,
        "contexto": contexto,
        "conceitos_chave": conceitos_chave,
        "perguntas": perguntas,
        "related_items": related_items,
        "sources": sources,
        "generation_failed": generation_failed,
    }
