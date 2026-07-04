from openai import OpenAI

from src.core.config import settings
from src.rag.curador import curar
from src.rag.reflect_prompt import (
    build_reflect_messages,
    needs_medical_caveat,
    parse_reflect_json,
)
from src.rag.retriever import retrieve

_NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec passagens suficientemente relacionadas "
    "à situação descrita."
)

GENERATION_FAILED_MESSAGE = "Não foi possível gerar uma resposta agora. Por favor, tente novamente em instantes."

CAP_ROUNDS = 5  # after this many completed rounds, force closing regardless of the model's own judgment

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def reflect(situation: str, conversation_history: list[dict] | None = None) -> dict:
    history = conversation_history or []
    try:
        chunks = retrieve(situation, top_k=5)
    except Exception:
        return {
            "opening": "",
            "doctrine_connection": GENERATION_FAILED_MESSAGE,
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": False,
            "generation_failed": True,
        }

    if not chunks:
        return {
            "opening": "",
            "doctrine_connection": _NOT_FOUND_MESSAGE,
            "reflection_questions": [],
            "complementary_items": [],
            "sources": [],
            "not_found": True,
            "generation_failed": False,
        }

    primary = chunks[:2]
    complementary_raw = chunks[2:5]

    combined_text = situation + " " + " ".join(h["content"] for h in history)
    add_caveat = needs_medical_caveat(combined_text)
    force_closing = len(history) // 2 >= CAP_ROUNDS
    system, messages = build_reflect_messages(
        situation, primary, add_caveat, history=history
    )

    opening = ""
    doctrine_connection = ""
    reflection_questions = []
    is_closing = False
    generation_failed = False
    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        opening, doctrine_connection, reflection_questions, is_closing = (
            parse_reflect_json(response.choices[0].message.content)
        )
    except Exception:
        generation_failed = True

    if force_closing:
        is_closing = True
        reflection_questions = []

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
            "excerpt": c["content"],
        }
        for c in primary
    ]

    complementary_items = curar(situation, complementary_raw)

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
