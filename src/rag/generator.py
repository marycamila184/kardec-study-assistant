import anthropic

from src.core.config import settings
from src.rag.prompt import build_messages
from src.rag.retriever import retrieve

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec informações suficientes para responder "
    "a essa pergunta. Por favor, reformule sua dúvida ou consulte diretamente as obras."
)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def condense_query(question: str, history: list[dict]) -> str:
    history_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}"
        for t in history[-settings.max_history_turns :]
    )
    prompt = (
        f"Dado este histórico de conversa:\n{history_text}\n\n"
        f"Reescreva a seguinte pergunta como uma consulta de busca independente e completa. "
        f"Retorne apenas a consulta reescrita, sem explicações.\n\nPergunta: {question}"
    )
    response = _get_client().messages.create(
        model=settings.condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate(question: str, history: list[dict]) -> dict:
    search_query = condense_query(question, history) if history else question
    chunks = retrieve(search_query)

    if not chunks:
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "not_found": True}

    system, messages = build_messages(question, chunks, history, settings.max_history_turns)
    response = _get_client().messages.create(
        model=settings.chat_model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    seen: set[tuple] = set()
    sources = []
    for chunk in chunks:
        m = chunk["metadata"]
        key = (m["book"], m.get("chapter_title", ""), m.get("item_number", ""))
        if key not in seen:
            seen.add(key)
            sources.append({
                "book": m["book"],
                "chapter": m.get("chapter_title") or None,
                "item_number": m.get("item_number") or None,
            })

    return {
        "answer": response.content[0].text,
        "sources": sources,
        "not_found": False,
    }
