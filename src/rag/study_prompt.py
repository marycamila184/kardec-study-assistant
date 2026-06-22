import json
import re

_SYSTEM_TEMPLATE = """\
Você é um educador especializado na obra de Allan Kardec. Baseando-se SOMENTE nos \
trechos abaixo, retorne APENAS um JSON válido com as chaves exatas:
{{
  "explanation": "<explicação em linguagem moderna incluindo conexões com as referências>",
  "practical_example": "<exemplo prático da vida cotidiana>"
}}

Nunca elabore doutrina além dos trechos. Se o trecho for muito breve, diga isso \
explicitamente dentro do JSON. Se o tema não estiver nos livros, diga que não encontrou.

[TRECHO PRINCIPAL]
{main_passage}

[REFERÊNCIAS RELACIONADAS]
{related_passages}"""


def _format_related(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma)"
    parts = []
    for c in chunks:
        m = c["metadata"]
        parts.append(f"[{m['book']} | Item {m['item_number']}]\n\"{c['content']}\"")
    return "\n\n".join(parts)


def build_study_messages(main_text: str, related_chunks: list[dict]) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        main_passage=main_text,
        related_passages=_format_related(related_chunks),
    )
    messages = [{"role": "user", "content": "Explique o trecho acima."}]
    return system, messages


def parse_llm_json(text: str) -> tuple[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()
    try:
        data = json.loads(text)
        return data.get("explanation", ""), data.get("practical_example", "")
    except (json.JSONDecodeError, AttributeError):
        return text, ""
