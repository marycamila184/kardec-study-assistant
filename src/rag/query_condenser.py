from src.core.config import settings
from src.rag.llm_client import get_client

ANCHOR_CAP = 500


def blend_anchor(query: str, anchor_text: str | None) -> str:
    """Bias retrieval toward the passage the user is studying by prepending its
    text (capped at ANCHOR_CAP) to the search query. Retrieval-only: the anchor
    never reaches the prompt, sources, or displayed output. Returns query
    unchanged when there is no usable anchor."""
    if not anchor_text or not anchor_text.strip():
        return query
    return f"{anchor_text.strip()[:ANCHOR_CAP]}\n{query}"


def condense_query(question: str, history: list[dict]) -> str:
    history_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in history[-settings.max_history_turns :]
    )
    prompt = (
        f"Dado este histórico de conversa:\n{history_text}\n\n"
        f"Reescreva a seguinte pergunta como uma consulta de busca independente e completa. "
        f"Mantenha a consulta em português (Brasil) e preserve os termos doutrinários "
        f"espíritas usados na conversa (ex.: reencarnação, perispírito, expiação) — "
        f"não os substitua por sinônimos genéricos. "
        f"Retorne apenas a consulta reescrita, sem explicações.\n\nPergunta: {question}"
    )
    response = get_client().chat.completions.create(
        model=settings.resolved_condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
