import re

_SYSTEM_TEMPLATE = """\
Você é um especialista nas obras de Allan Kardec.

Escreva um resumo de 2 a 4 frases em português descrevendo do que trata o \
capítulo abaixo — o tema geral, não um item específico.

Regras estritas:
- Baseie-se SOMENTE no texto fornecido. Nunca invente ou generalize além dele.
- Nunca personifique "o Espiritismo" como um agente que faz ou valoriza coisas \
— atribua afirmações doutrinárias ao texto, ao capítulo ou a Kardec.
- Não cite números de item específicos.
- Responda SOMENTE com o texto do resumo — sem markdown, sem aspas, sem \
texto antes ou depois.

[CAPÍTULO: {chapter_title}]
{chapter_text}"""


def build_chapter_summary_messages(
    chapter_title: str, chapter_text: str
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        chapter_title=chapter_title,
        chapter_text=chapter_text[:8000],
    )
    messages = [{"role": "user", "content": "Resuma do que trata este capítulo."}]
    return system, messages


def clean_chapter_summary(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip()).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].strip()
    return text
