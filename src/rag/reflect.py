import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor

from src.core.config import settings
from src.rag.crisis import (
    CRISIS_EXIT_MESSAGE,
    CRISIS_NOTE,
    mentions_suicide_topic,
    needs_crisis_note,
    needs_medical_caveat,
)
from src.rag.curador import curar
from src.rag.llm_client import create_json_completion, get_client
from src.rag.query_condenser import blend_anchor, condense_query
from src.rag.reflect_prompt import build_reflect_messages, parse_reflect_json
from src.rag.retriever import (
    REFLECT_BOOKS,
    append_chapter_commentary,
    filter_sensitive_chunks,
    has_real_item_number,
    retrieve,
)
from src.rag.sensitivity import classify_sensitivity

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

_SENSITIVITY_TIMEOUT_S = 8.0


def _crisis_exit() -> dict:
    """Fixed, deterministic crisis response for /reflect — no retrieval, no
    citations, no reflection questions. Never depends on the generation LLM."""
    return {
        "opening": "",
        "doctrine_connection": CRISIS_EXIT_MESSAGE,
        "reflection_questions": [],
        "is_closing": False,
        "complementary_items": [],
        "sources": [],
        "not_found": False,
        "generation_failed": False,
        "safety_level": "crise",
    }


def reflect(
    situation: str,
    conversation_history: list[dict] | None = None,
    anchor_text: str | None = None,
) -> dict:
    history = conversation_history or []
    combined_text = situation + " " + " ".join(h["content"] for h in history)

    # Deterministic crisis floor: a keyword hit short-circuits to the fixed exit
    # before any retrieval or classifier call — never gated on the LLM.
    if needs_crisis_note(combined_text):
        return _crisis_exit()

    # Topic-level mention this turn (no ideation — that exited above): reflect
    # normally, but always append the CVV note in code. Current turn only, so
    # a thread that once mentioned the topic doesn't repeat the note forever.
    topic_note = mentions_suicide_topic(situation)

    executor = ThreadPoolExecutor(max_workers=1)
    sensitivity_future = executor.submit(classify_sensitivity, situation)
    try:
        search_query = situation
        if history:
            try:
                search_query = condense_query(situation, history)
            except Exception:
                logger.exception(
                    "condense_query failed in /reflect; using raw situation"
                )
                search_query = situation
        search_query = blend_anchor(search_query, anchor_text)

        try:
            chunks = retrieve(search_query, top_k=5, book_filter=list(REFLECT_BOOKS))
        except Exception:
            logger.exception("retrieve failed in /reflect")
            return {
                "opening": "",
                "doctrine_connection": GENERATION_FAILED_MESSAGE,
                "reflection_questions": [],
                "complementary_items": [],
                "sources": [],
                "not_found": False,
                "generation_failed": True,
                "safety_level": "normal",
            }

        try:
            level = sensitivity_future.result(timeout=_SENSITIVITY_TIMEOUT_S)
        except Exception:
            logger.exception("classify_sensitivity slow/failed; defaulting to normal")
            level = "normal"
    finally:
        executor.shutdown(wait=False)

    if level == "crise":
        return _crisis_exit()

    if level == "abalo":
        # The chapter half is a no-op here (REFLECT_BOOKS excludes O Céu e o
        # Inferno), but the content half is live: it drops suicide-adjacent
        # passages that exist inside ESE/LE too (e.g. "abreviar as misérias"),
        # so they are never introduced to a distressed reader unprompted. The
        # other abalo behaviors (gentle prompt, caveat, chip suppression)
        # still apply below.
        chunks = filter_sensitive_chunks(chunks)

    if not chunks:
        logger.warning("no chunks retrieved for /reflect; returning not_found")
        return {
            "opening": "",
            "doctrine_connection": (
                _NOT_FOUND_MESSAGE + "\n\n" + CRISIS_NOTE
                if topic_note
                else _NOT_FOUND_MESSAGE
            ),
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": True,
            "generation_failed": False,
            "safety_level": level,
        }

    primary = append_chapter_commentary(chunks[:2])
    complementary_raw = chunks[2:5]

    add_caveat = needs_medical_caveat(combined_text) or level == "abalo"
    force_closing = len(history) // 2 >= CAP_ROUNDS
    system, messages = build_reflect_messages(
        situation, primary, add_caveat, history=history, force_closing=force_closing
    )

    def _call_reflexivo():
        response = create_json_completion(
            get_client(),
            model=settings.resolved_chat_model,
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        reflexivo_future = pool.submit(_call_reflexivo)
        curador_future = pool.submit(curar, situation, complementary_raw)

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

    if not generation_failed and not reflection_questions:
        # Contract hardening: the prompt allows only two shapes — 1–3 questions,
        # or a closing. A successful turn with zero questions IS a closing even
        # when the model forgets to set the flag.
        is_closing = True

    if topic_note:
        # Deterministic safety property: a suicide-topic turn ALWAYS carries
        # the CVV note — even when generation failed (matches /chat).
        doctrine_connection = (
            doctrine_connection + "\n\n" + CRISIS_NOTE
            if doctrine_connection
            else CRISIS_NOTE
        )

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
        "safety_level": level,
    }
