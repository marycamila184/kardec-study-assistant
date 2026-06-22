from openai import OpenAI

from src.core.config import settings
from src.rag.prompt import build_messages
from src.rag.retriever import retrieve

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec informações suficientes para responder "
    "a essa pergunta. Por favor, reformule sua dúvida ou consulte diretamente as obras."
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
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
    response = _get_client().chat.completions.create(
        model=settings.condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def generate(question: str, history: list[dict]) -> dict:
    search_query = condense_query(question, history) if history else question
    chunks = retrieve(search_query)

    if not chunks:
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "not_found": True}

    system, messages = build_messages(
        question, chunks, history, settings.max_history_turns
    )
    response = _get_client().chat.completions.create(
        model=settings.chat_model,
        max_tokens=1024,
        messages=[{"role": "system", "content": system}] + messages,
    )

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
                    "item_number": m.get("item_number") or None,
                }
            )

    return {
        "answer": response.choices[0].message.content,
        "sources": sources,
        "not_found": False,
    }
