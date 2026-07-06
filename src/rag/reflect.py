import concurrent.futures
import logging

from src.core.config import settings
from src.rag.curador import curar
from src.rag.llm_client import get_client
from src.rag.query_condenser import condense_query
from src.rag.reflect_prompt import (
    CRISIS_NOTE,
    build_reflect_messages,
    needs_crisis_note,
    needs_medical_caveat,
    parse_reflect_json,
)
from src.rag.retriever import has_real_item_number, retrieve

logger = logging.getLogger(__name__)

_NOT_FOUND_MESSAGE = (
    "Obrigado por confiar e compartilhar o que você está vivendo. Desta vez não "
    "encontrei nas obras de Kardec passagens próximas o bastante da sua situação "
    "para propor uma reflexão bem fundamentada — e prefiro não improvisar. Se "
    "quiser, descreva a situação com outras palavras, ou visite o modo Abrir o "
    "Evangelho para a leitura do dia."
)

GENERATION_FAILED_MESSAGE = "Não foi possível gerar uma resposta agora. Por favor, tente novamente em instantes."

CAP_ROUNDS = 5  # after this many completed rounds, force closing regardless of the model's own judgment


def _with_crisis_note(text: str, crisis: bool) -> str:
    if not crisis:
        return text
    return f"{text}\n\n{CRISIS_NOTE}" if text else CRISIS_NOTE


def reflect(situation: str, conversation_history: list[dict] | None = None) -> dict:
    history = conversation_history or []
    combined_text = situation + " " + " ".join(h["content"] for h in history)
    crisis = needs_crisis_note(combined_text)
    search_query = situation
    if history:
        try:
            search_query = condense_query(situation, history)
        except Exception:
            logger.exception("condense_query failed in /reflect; using raw situation")
            search_query = situation
    try:
        chunks = retrieve(search_query, top_k=5)
    except Exception:
        logger.exception("retrieve failed in /reflect")
        return {
            "opening": "",
            "doctrine_connection": _with_crisis_note(GENERATION_FAILED_MESSAGE, crisis),
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": False,
            "generation_failed": True,
        }

    if not chunks:
        logger.warning("no chunks retrieved for /reflect; returning not_found")
        return {
            "opening": "",
            "doctrine_connection": _with_crisis_note(_NOT_FOUND_MESSAGE, crisis),
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": True,
            "generation_failed": False,
        }

    primary = chunks[:2]
    complementary_raw = chunks[2:5]

    add_caveat = needs_medical_caveat(combined_text) or crisis
    force_closing = len(history) // 2 >= CAP_ROUNDS
    system, messages = build_reflect_messages(
        situation, primary, add_caveat, history=history, force_closing=force_closing
    )

    def _call_reflexivo():
        response = get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return parse_reflect_json(response.choices[0].message.content)

    opening = ""
    doctrine_connection = ""
    reflection_questions = []
    is_closing = False
    generation_failed = False

    # curar() makes its own independent Groq call and only needs
    # `complementary_raw`, which is already retrieved — run both LLM calls
    # concurrently instead of paying their latency twice in sequence.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        reflexivo_future = executor.submit(_call_reflexivo)
        curador_future = executor.submit(curar, situation, complementary_raw)

        try:
            opening, doctrine_connection, reflection_questions, is_closing = (
                reflexivo_future.result()
            )
        except Exception:
            logger.exception("reflexivo LLM call/parse failed")
            generation_failed = True

        complementary_items = curador_future.result()

    if force_closing:
        is_closing = True
        reflection_questions = []

    doctrine_connection = _with_crisis_note(doctrine_connection, crisis)

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": (
                c["metadata"]["item_number"]
                if has_real_item_number(c["metadata"].get("item_number"))
                else None
            ),
            "excerpt": c["content"],
        }
        for c in primary
    ]

    return {
        "opening": opening,
        "doctrine_connection": doctrine_connection,
        "reflection_questions": reflection_questions,
        "is_closing": is_closing,
        "complementary_items": complementary_items,
        "sources": sources,
        "not_found": False,
        "generation_failed": generation_failed,
    }
