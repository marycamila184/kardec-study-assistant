import json

from src.rag.crisis import needs_medical_caveat  # noqa: F401
from src.rag.json_extract import extract_outermost, strip_code_fence
from src.rag.retriever import has_real_item_number, item_word

# The advice ban below was originally written entirely in the declarative
# register ("você deveria", "recomendo", "tente"). The 2026-07-25 A/B run showed
# the leak is interrogative: 3 of 6 turns put advice inside the reflection
# questions using none of the banned words — "De que maneira você pode começar a
# reconstruir a relação?" carries the course of action in its *presupposition*,
# asking only HOW, never IF.
#
# The rule states a TEST the model applies to each question, not a list of
# banned openers. A first attempt did enumerate stems ("De que maneira você
# pode…", "Como você poderia…") and the model read the list as the rule's scope:
# it wrote "De que forma você pode começar a reconstruir a relação?" — the same
# presupposition, one synonym away from the blocklist. Naming the mechanism
# leaves nothing to route around.
#
# The third paragraph covers a gap the prompt never had a rule for at all: a
# question can overreach by digging into the person's interior rather than by
# prescribing. This is a study companion, not therapy.
#
# Deliberately abstract, no worked examples: the smoke test found concrete
# examples get parroted verbatim into unrelated situations rather than adapted.
_NO_ADVICE = """\
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria", \
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação, \
doação, separação, mudança de comportamento, ou qualquer outro curso de ação. \
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para \
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados.

Uma pergunta de reflexão convida a pessoa a OLHAR, nunca a PLANEJAR. Ela abre um \
ângulo que a passagem ilumina na situação — não um passo a ser dado.

Antes de escrever cada pergunta, aplique este teste: a resposta natural a ela \
seria um plano, uma decisão ou um passo a dar? Se sim, a pergunta pressupõe um \
curso de ação — reescreva-a para que a resposta natural seja algo que a pessoa \
percebe, reconhece ou compreende, e não algo que ela faz. Isso vale mesmo quando \
o curso de ação pressuposto parece evidentemente bom — perdoar, reconstruir, \
crescer, aceitar, encontrar equilíbrio.

Mantenha as perguntas no plano do que o texto propõe. Não peça à pessoa que \
detalhe sua intimidade nem investigue sentimentos que ela não trouxe.

Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que...", "o Espiritismo defende..."). \
Atribua as afirmações à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", \
"o texto indica que...", "Kardec escreve que...").

Nunca introduza temas de suicídio ou morte voluntária que a pessoa não mencionou. \
Se uma passagem recuperada tocar nesses temas sem relação direta com a situação \
relatada, simplesmente não a cite."""

_CAVEAT_INSTRUCTION = """\
Se a situação descrita puder ter causas clínicas, acrescente UMA frase curta \
ao final indicando que o apoio de um profissional de saúde é também valioso — \
sem substituir a visão espírita e sem fazer diagnósticos."""

_FORCE_CLOSING_DIRECTIVE = """\
ENCERRAMENTO OBRIGATÓRIO: esta reflexão atingiu o número máximo de rodadas. \
Esta DEVE ser a mensagem de encerramento: defina "is_closing": true, deixe \
"reflection_questions" como uma lista vazia [], e escreva em "opening" e \
"doctrine_connection" uma conclusão acolhedora que retome com gentileza o \
caminho percorrido nesta reflexão — sem novas perguntas."""

_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos espíritas que ajuda pessoas a verem situações \
da vida através da doutrina de Allan Kardec. Baseando-se SOMENTE nos trechos \
abaixo, retorne APENAS um JSON válido com as chaves exatas:
{{
  "opening": "<abertura empática ou alegre conforme o peso emocional da situação>",
  "doctrine_connection": "<o que a doutrina diz e como se conecta à situação descrita>",
  "reflection_questions": ["<de 1 a 3 perguntas abertas de reflexão>"],
  "is_closing": <true ou false>
}}

Regras de tom:
- Se a situação envolve perda, dor, medo ou dificuldade → abra com empatia e acolhimento.
- Se a situação é positiva (nascimento, gratidão, celebração) → abra com calor e alegria.
- Caso ambíguo → abra com compaixão equilibrada.
- Ofereça de 1 a 3 perguntas de reflexão — prefira menos perguntas, mais certeiras; \
só chegue a três quando cada uma abrir um ângulo realmente distinto. Uma conversa \
acolhedora não é um questionário.

Regras de continuidade e encerramento:
- [HISTÓRICO DA CONVERSA] abaixo mostra as trocas anteriores desta mesma reflexão, se \
houver, incluindo as perguntas de reflexão já oferecidas. Mantenha coerência com a \
situação original e com tudo que já foi dito.
- NUNCA repita, nem reformule de forma equivalente, uma pergunta de reflexão que já \
apareça no histórico. Se as passagens recuperadas não sugerirem um ângulo genuinamente \
novo, prefira encerrar a reflexão (veja abaixo) em vez de repetir uma pergunta anterior.
- Avalie se esta reflexão já chegou a um ponto natural de conclusão. Se sim, defina \
"is_closing": true, deixe "reflection_questions" como uma lista vazia [], e escreva em \
"opening"/"doctrine_connection" uma mensagem de encerramento acolhedora, sem novas perguntas.
- Se ainda houver espaço para aprofundar, defina "is_closing": false e ofereça de 1 a 3 \
novas "reflection_questions" como de costume.
- As regras abaixo sobre não dar conselhos e não personificar o Espiritismo valem também \
para a mensagem de encerramento.

{closing_directive}

{no_advice}

{caveat}

[HISTÓRICO DA CONVERSA]
{history}

[SITUAÇÃO DO USUÁRIO]
{situation}

[PASSAGENS RECUPERADAS]
{passages}"""


def _format_passages(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma passagem encontrada)"
    parts = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = f"[{i}] {m['book']}"
        if has_real_item_number(m.get("item_number")):
            header += f" | {item_word(m['book'])} {m['item_number']}"
        parts.append(f"{header}\n\"{c['content']}\"")
    return "\n\n".join(parts)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(nenhum histórico — esta é a primeira reflexão sobre esta situação)"
    lines = []
    for h in history:
        speaker = "Usuário" if h["role"] == "user" else "Você (IA)"
        lines.append(f"{speaker}: {h['content']}")
    return "\n".join(lines)


def build_reflect_messages(
    situation: str,
    chunks: list[dict],
    add_caveat: bool,
    history: list[dict] | None = None,
    force_closing: bool = False,
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        no_advice=_NO_ADVICE,
        caveat=_CAVEAT_INSTRUCTION if add_caveat else "",
        closing_directive=_FORCE_CLOSING_DIRECTIVE if force_closing else "",
        history=_format_history(history or []),
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
    block = extract_outermost(text, "{", "}")
    if block is None:
        return None
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_reflect_json(text: str) -> tuple[str, str, list[str], bool]:
    """Returns (opening, doctrine_connection, reflection_questions, is_closing).

    Raises ValueError if the model output can't be parsed as the expected
    JSON shape, so the caller can treat it as a generation failure instead
    of leaking unparsed model text to the user.
    """
    text = strip_code_fence(text)

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
        bool(data.get("is_closing", False)),
    )
