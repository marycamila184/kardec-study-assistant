import logging

from src.core.config import settings
from src.rag.curador_prompt import build_curador_messages, parse_curador_json
from src.rag.llm_client import get_client

logger = logging.getLogger(__name__)


def curar(main_text: str, candidates: list[dict]) -> list[dict]:
    """
    Given a main passage and candidate related chunks, returns the candidates
    annotated with a doctrinal connection phrase ("conexao").

    Falls back to unannotated candidates if the LLM call itself fails. If the
    call succeeds but the model legitimately finds no relevant candidate, an
    empty list is returned instead — the two cases are not the same, and
    showing all raw candidates when the model said "none of these fit" would
    misrepresent its judgment.
    """
    if not candidates:
        return []

    system, messages = build_curador_messages(main_text, candidates)

    call_failed = False
    try:
        response = get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=512,
            messages=[{"role": "system", "content": system}] + messages,
        )
        selections = parse_curador_json(response.choices[0].message.content)
    except Exception:
        logger.exception("curador call/parse failed; falling back to raw candidates")
        call_failed = True
        selections = []

    if call_failed:
        return [
            {
                "book": c["metadata"]["book"],
                "chapter": c["metadata"].get("chapter"),
                "item_number": c["metadata"]["item_number"],
                "preview": c["content"][:200],
                "conexao": None,
            }
            for c in candidates
        ]

    if not selections:
        return []

    result = []
    for sel in selections:
        idx = sel["index"]
        if 0 <= idx < len(candidates):
            c = candidates[idx]
            result.append(
                {
                    "book": c["metadata"]["book"],
                    "chapter": c["metadata"].get("chapter"),
                    "item_number": c["metadata"]["item_number"],
                    "preview": c["content"][:200],
                    "conexao": sel["conexao"] or None,
                }
            )

    return result
