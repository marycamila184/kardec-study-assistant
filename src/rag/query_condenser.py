from src.core.config import settings
from src.rag.llm_client import get_client


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
    response = get_client().chat.completions.create(
        model=settings.condenser_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
