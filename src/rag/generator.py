import logging
import random
import re

from src.core.config import settings
from src.rag.llm_client import get_client
from src.rag.mode_detector import extract_study_reference, is_smalltalk
from src.rag.prompt import build_messages
from src.rag.query_condenser import blend_anchor, condense_query
from src.rag.reflect_prompt import CRISIS_NOTE, needs_crisis_note, needs_medical_caveat
from src.rag.retriever import (
    EVANGELHO_BOOK,
    append_chapter_commentary,
    has_real_item_number,
    retrieve,
    retrieve_by_item,
)

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec passagens que respondam com segurança a essa "
    "pergunta — e prefiro não inventar doutrina. Tente perguntar com outras palavras: "
    "às vezes um termo diferente encontra o trecho certo. Se preferir navegar pelo "
    "texto, o modo Estudar uma Obra permite abrir qualquer questão diretamente."
)

BOOK_FALLBACK_NOTE = (
    "Não encontrei citações específicas sobre esse tema em *{book}*. "
    "Porém, outras obras de Kardec abordam o assunto:\n\n"
)

GENERATION_FAILED_MESSAGE = "Não foi possível gerar uma resposta agora. Por favor, tente novamente em instantes."

# Brief warm replies for pure acknowledgment / closing messages (see
# is_smalltalk). No retrieval, no LLM, no source chips — just a human closing.
SMALLTALK_REPLIES = (
    "De nada! Fico feliz em ajudar. 🙏",
    "Imagina! Estou por aqui sempre que surgir outra dúvida.",
    "Por nada! Que bom poder acompanhar seus estudos.",
    "De nada! Sempre que quiser aprofundar, é só chamar.",
)


def _with_crisis_note(text: str, crisis: bool) -> str:
    if not crisis:
        return text
    return f"{text}\n\n{CRISIS_NOTE}" if text else CRISIS_NOTE


# Tolerant of the model mangling the trailer: an optional leading "[" or stray
# "/", optional closing "]", and whitespace around the colon — so variants like
# "/FONTES:", "FONTES: 1, 3" or "[FONTES:]" are stripped instead of leaking into
# the answer. Uppercase-only (no re.IGNORECASE) so prose like "as fontes:" is
# never mistaken for the marker. Anchored to end; body stops at a newline so the
# two markers on separate lines are matched one per loop pass.
_FONTES_MARKER = re.compile(r"\s*[\[/]?\s*FONTES\s*:\s*([^\]\n]*)\]?\s*\.?\s*$")
_SEGUIR_MARKER = re.compile(r"\s*[\[/]?\s*SEGUIR\s*:\s*([^\]\n]*)\]?\s*\.?\s*$")


def _cited_chunks(marker_body: str, chunks: list[dict]) -> list[dict]:
    """Resolves the [FONTES: 1, 3] body to the chunks the model says it used
    (1-based indices matching the prompt's passage numbering). Fallbacks keep
    the citation chips honest without ever losing them to a malformed marker:
    - marker with only invalid indices → all chunks;
    - explicitly empty marker → no sources (the model used none).
    """
    indices = [int(t) for t in re.findall(r"\d+", marker_body)]
    if not indices:
        return []
    cited = [c for i, c in enumerate(chunks, 1) if i in set(indices)]
    return cited or chunks


def _strip_trailing_markers(
    answer: str, chunks: list[dict]
) -> tuple[str, list[dict], list[str]]:
    """Strips the prompt-mandated [FONTES] and [SEGUIR] trailer lines off the
    answer, in whichever order the model emitted them. Returns
    (answer, cited_chunks, suggested_questions); a missing marker leaves its
    output at the safe default (all chunks / no suggestions)."""
    suggestions: list[str] = []
    for _ in range(2):
        m = _SEGUIR_MARKER.search(answer)
        if m:
            answer = answer[: m.start()].rstrip()
            suggestions = [q.strip() for q in m.group(1).split("|") if q.strip()][:2]
            continue
        m = _FONTES_MARKER.search(answer)
        if m:
            answer = answer[: m.start()].rstrip()
            chunks = _cited_chunks(m.group(1), chunks)
            continue
        break
    return answer, chunks, suggestions


def _direct_item_chunks(question: str, book_filter: str | None) -> list[dict]:
    """Deterministic lookup for item-reference questions ("questão 132 do
    Livro dos Espíritos"). Semantic search can't reliably find an item by
    its number, so when the question names a specific item and the book is
    known (named in the question, or implied by an active book filter),
    fetch that item's chunks directly. Returns [] when not applicable."""
    ref = extract_study_reference(question)
    book = ref["book"] or book_filter
    if not (ref["item_number"] and book):
        return []
    if book == EVANGELHO_BOOK:
        # "item N do Evangelho" is ambiguous — item numbers repeat across ~28
        # chapters, so a chapterless direct lookup would return them all. Defer
        # to (enriched) semantic retrieval instead.
        return []
    try:
        return retrieve_by_item(book, ref["item_number"])
    except Exception:
        logger.exception("direct item lookup failed in /chat generate")
        return []


def generate(
    question: str,
    history: list[dict],
    book_filter: str | None = None,
    anchor_text: str | None = None,
) -> dict:
    # A pure "obrigada / entendi / valeu" needs a warm closing, not a doctrinal
    # answer with source chips. Short-circuit before any retrieval or LLM call.
    # (Crisis takes priority — such a message is never mere small talk anyway.)
    if is_smalltalk(question) and not needs_crisis_note(question):
        return {
            "answer": random.choice(SMALLTALK_REPLIES),
            "sources": [],
            "suggested_questions": [],
            "not_found": False,
            "generation_failed": False,
        }

    crisis = needs_crisis_note(question)
    search_query = question
    if history:
        try:
            search_query = condense_query(question, history)
        except Exception:
            logger.exception("condense_query failed in /chat; using raw question")
            search_query = question

    search_query = blend_anchor(search_query, anchor_text)

    direct_chunks = _direct_item_chunks(question, book_filter)

    try:
        chunks = retrieve(search_query, book_filter=book_filter)
    except Exception:
        logger.exception("retrieve failed in /chat generate")
        if not direct_chunks:
            return {
                "answer": _with_crisis_note(GENERATION_FAILED_MESSAGE, crisis),
                "sources": [],
                "suggested_questions": [],
                "not_found": False,
                "generation_failed": True,
            }
        chunks = []

    if direct_chunks:
        # The referenced item leads the passage list; drop any semantic
        # duplicates of it so the prompt never repeats the same text.
        direct_keys = {
            (c["metadata"]["book"], c["metadata"]["item_number"]) for c in direct_chunks
        }
        chunks = direct_chunks + [
            c
            for c in chunks
            if (c["metadata"]["book"], c["metadata"]["item_number"]) not in direct_keys
        ]

    fallback_note: str | None = None
    if not chunks and book_filter:
        try:
            fallback_chunks = retrieve(search_query)
        except Exception:
            logger.exception("book-filter fallback retrieve failed")
            fallback_chunks = []
        if fallback_chunks:
            chunks = fallback_chunks
            fallback_note = BOOK_FALLBACK_NOTE.format(book=book_filter)
            logger.info(
                "book_filter %s empty; fell back to full-collection search",
                book_filter,
            )

    chunks = append_chapter_commentary(chunks)

    if not chunks:
        logger.warning("no chunks retrieved for /chat; returning not_found")
        return {
            "answer": _with_crisis_note(NOT_FOUND_MESSAGE, crisis),
            "sources": [],
            "suggested_questions": [],
            "not_found": True,
            "generation_failed": False,
        }

    add_caveat = needs_medical_caveat(question) or crisis
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
        answer, chunks, suggested_questions = _strip_trailing_markers(answer, chunks)
        if fallback_note:
            answer = fallback_note + answer
        generation_failed = False
    except Exception:
        logger.exception("chat generation LLM call failed")
        answer = GENERATION_FAILED_MESSAGE
        suggested_questions = []
        generation_failed = True

    if crisis:
        # A crisis conversation must not be steered toward "explore more"
        # chips; the CVV note is the only thing appended.
        suggested_questions = []

    answer = _with_crisis_note(answer, crisis)

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
                    # chapter_ref is the machine chapter id ("CAPÍTULO II"),
                    # the value /study's retrieve_by_item filters on —
                    # distinct from the display title in "chapter".
                    "chapter_ref": m.get("chapter") or None,
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
        "suggested_questions": suggested_questions,
        "not_found": False,
        "generation_failed": generation_failed,
    }
