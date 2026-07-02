import json
import re

CLINICAL_KEYWORDS = [
    "vozes",
    "sombras",
    "escuto",
    "vejo entidades",
    "ouço",
    "pânico",
    "desespero",
    "não consigo dormir",
    "alucinação",
]

_NO_ADVICE = """\
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria", \
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação, \
doação, separação, mudança de comportamento, ou qualquer outro curso de ação. \
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para \
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados.

Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que...", "o Espiritismo defende..."). \
Atribua as afirmações à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", \
"o texto indica que...", "Kardec escreve que...")."""

_CAVEAT_INSTRUCTION = """\
Se a situação descrita puder ter causas clínicas, acrescente UMA frase curta \
ao final indicando que o apoio de um profissional de saúde é também valioso — \
sem substituir a visão espírita e sem fazer diagnósticos."""

_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos espíritas que ajuda pessoas a verem situações \
da vida através da doutrina de Allan Kardec. Baseando-se SOMENTE nos trechos \
abaixo, retorne APENAS um JSON válido com as chaves exatas:
{{
  "opening": "<abertura empática ou alegre conforme o peso emocional da situação>",
  "doctrine_connection": "<o que a doutrina diz e como se conecta à situação descrita>",
  "reflection_questions": ["<pergunta 1>", "<pergunta 2>", "<pergunta 3>"]
}}

Regras de tom:
- Se a situação envolve perda, dor, medo ou dificuldade → abra com empatia e acolhimento.
- Se a situação é positiva (nascimento, gratidão, celebração) → abra com calor e alegria.
- Caso ambíguo → abra com compaixão equilibrada.

{no_advice}

{caveat}

[SITUAÇÃO DO USUÁRIO]
{situation}

[PASSAGENS RECUPERADAS]
{passages}"""


def needs_medical_caveat(situation: str) -> bool:
    lower = situation.lower()
    return any(kw in lower for kw in CLINICAL_KEYWORDS)


def _format_passages(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma passagem encontrada)"
    parts = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = f"[{i}] {m['book']}"
        if m.get("item_number"):
            header += f" | Item {m['item_number']}"
        parts.append(f"{header}\n\"{c['content']}\"")
    return "\n\n".join(parts)


def build_reflect_messages(
    situation: str, chunks: list[dict], add_caveat: bool
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        no_advice=_NO_ADVICE,
        caveat=_CAVEAT_INSTRUCTION if add_caveat else "",
        situation=situation,
        passages=_format_passages(chunks),
    )
    messages = [
        {
            "role": "user",
            "content": "Veja essa situação pela lente da doutrina espírita.",
        }
    ]
    return system, messages


def _extract_json_object(text: str) -> dict | None:
    """Find and parse the outermost {...} block in text, if any."""
    start = text.find("{")
    if start == -1:
        return None
    depth, end = 0, -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_reflect_json(text: str) -> tuple[str, str, list[str]]:
    """Returns (opening, doctrine_connection, reflection_questions).

    Raises ValueError if the model output can't be parsed as the expected
    JSON shape, so the caller can treat it as a generation failure instead
    of leaking unparsed model text to the user.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()

    data = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            data = parsed
    except json.JSONDecodeError:
        pass
    if data is None:
        data = _extract_json_object(text)

    if data is None:
        raise ValueError("could not parse reflect JSON response")

    return (
        data.get("opening", ""),
        data.get("doctrine_connection", ""),
        data.get("reflection_questions", []),
    )
