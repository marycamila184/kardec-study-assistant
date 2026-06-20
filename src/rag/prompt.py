_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos da doutrina espírita, fundamentado exclusivamente \
nas cinco obras de Allan Kardec. Responda SOMENTE com base nas passagens recuperadas abaixo. \
Se as passagens não contiverem informação suficiente para responder, diga isso explicitamente \
— não invente doutrina.

Responda em Português (Brasil). Separe claramente o que vem do texto original e o que é \
sua explicação.

[PASSAGENS RECUPERADAS]
{passages}"""


def _format_passage(index: int, chunk: dict) -> str:
    m = chunk["metadata"]
    header = f"[{index}] Obra: {m['book']}"
    if m.get("chapter_title"):
        header += f" | Capítulo: {m['chapter_title']}"
    if m.get("item_number"):
        header += f" | Item: {m['item_number']}"
    return f"{header}\n    \"{chunk['content']}\""


def build_messages(
    question: str,
    chunks: list[dict],
    history: list[dict],
    max_history_turns: int = 10,
) -> tuple[str, list[dict]]:
    passages = "\n\n".join(_format_passage(i + 1, c) for i, c in enumerate(chunks))
    system = _SYSTEM_TEMPLATE.format(passages=passages)

    messages = [
        {"role": t["role"], "content": t["content"]}
        for t in history[-max_history_turns:]
    ]
    messages.append({"role": "user", "content": question})

    return system, messages
