from openai import OpenAI

from src.core.config import settings
from src.rag.curador_prompt import build_curador_messages, parse_curador_json

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def curar(main_text: str, candidates: list[dict]) -> list[dict]:
    """
    Given a main passage and candidate related chunks, returns the candidates
    annotated with a doctrinal connection phrase ("conexao").

    Falls back to unannotated candidates if the LLM call fails.
    """
    if not candidates:
        return []

    system, messages = build_curador_messages(main_text, candidates)

    try:
        response = _get_client().chat.completions.create(
            model=settings.chat_model,
            max_tokens=512,
            messages=[{"role": "system", "content": system}] + messages,
        )
        selections = parse_curador_json(response.choices[0].message.content)
    except Exception:
        selections = []

    if not selections:
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

    result = []
    for sel in selections:
        idx = sel["index"]
        if 0 <= idx < len(candidates):
            c = candidates[idx]
            result.append({
                "book": c["metadata"]["book"],
                "chapter": c["metadata"].get("chapter"),
                "item_number": c["metadata"]["item_number"],
                "preview": c["content"][:200],
                "conexao": sel["conexao"] or None,
            })

    return result
