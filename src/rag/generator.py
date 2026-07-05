import logging

from src.core.config import settings
from src.rag.llm_client import get_client
from src.rag.prompt import build_messages
from src.rag.query_condenser import condense_query
from src.rag.reflect_prompt import needs_medical_caveat
from src.rag.retriever import has_real_item_number, retrieve

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec informações suficientes para responder "
    "a essa pergunta. Por favor, reformule sua dúvida ou consulte diretamente as obras."
)

BOOK_FALLBACK_NOTE = (
    "Não encontrei citações específicas sobre esse tema em *{book}*. "
    "Porém, outras obras de Kardec abordam o assunto:\n\n"
)

GENERATION_FAILED_MESSAGE = "Não foi possível gerar uma resposta agora. Por favor, tente novamente em instantes."


def generate(
    question: str, history: list[dict], book_filter: str | None = None
) -> dict:
    search_query = question
    if history:
        try:
            search_query = condense_query(question, history)
        except Exception:
            search_query = question

    try:
        chunks = retrieve(search_query, book_filter=book_filter)
    except Exception:
        logger.exception("retrieve failed in /chat generate")
        return {
            "answer": GENERATION_FAILED_MESSAGE,
            "sources": [],
            "not_found": False,
            "generation_failed": True,
        }

    fallback_note: str | None = None
    if not chunks and book_filter:
        try:
            fallback_chunks = retrieve(search_query)
        except Exception:
            fallback_chunks = []
        if fallback_chunks:
            chunks = fallback_chunks
            fallback_note = BOOK_FALLBACK_NOTE.format(book=book_filter)
            logger.info(
                "book_filter %s empty; fell back to full-collection search",
                book_filter,
            )

    if not chunks:
        logger.warning("no chunks retrieved for /chat; returning not_found")
        return {
            "answer": NOT_FOUND_MESSAGE,
            "sources": [],
            "not_found": True,
            "generation_failed": False,
        }

    add_caveat = needs_medical_caveat(question)
    system, messages = build_messages(
        question, chunks, history, settings.max_history_turns, add_caveat=add_caveat
    )
    try:
        response = get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        answer = response.choices[0].message.content
        if fallback_note:
            answer = fallback_note + answer
        generation_failed = False
    except Exception:
        logger.exception("chat generation LLM call failed")
        answer = GENERATION_FAILED_MESSAGE
        generation_failed = True

    seen: set[tuple] = set()
    sources = []
    for chunk in chunks:
        m = chunk["metadata"]
        key = (m["book"], m.get("chapter_title", ""), m.get("item_number", ""))
        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "book": m["book"],
                    "chapter": m.get("chapter_title") or None,
                    "item_number": (
                        m["item_number"]
                        if has_real_item_number(m.get("item_number"))
                        else None
                    ),
                    "excerpt": chunk["content"],
                }
            )

    return {
        "answer": answer,
        "sources": [] if generation_failed else sources,
        "not_found": False,
        "generation_failed": generation_failed,
    }
