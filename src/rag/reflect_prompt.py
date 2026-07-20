import json

from src.rag.json_extract import extract_outermost, strip_code_fence
from src.rag.retriever import has_real_item_number

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

# Suicidal-ideation / self-harm cues. Matching any of these deterministically
# short-circuits both pipelines to the fixed crisis exit (CRISIS_EXIT_MESSAGE,
# which embeds CRISIS_NOTE) before any retrieval or LLM call — never left to the
# LLM's judgment. Includes unaccented variants because users often type without
# accents.
# First-person ideation / self-harm cues → deterministic fixed crisis exit.
# Bare topic words ("suicídio" alone) live in SUICIDE_TOPIC_KEYWORDS below:
# a doctrinal question about the topic gets a grounded answer + CRISIS_NOTE
# appended in code, never the fixed exit. Keep the two lists in sync: every
# ideation phrasing that contains a topic word must be listed here so it is
# caught BEFORE the topic path (callers check needs_crisis_note first).
CRISIS_KEYWORDS = [
    "me matar",
    "quero morrer",
    "queria morrer",
    "tirar minha vida",
    "tirar a minha vida",
    "acabar com minha vida",
    "acabar com a minha vida",
    "não quero mais viver",
    "nao quero mais viver",
    "não aguento mais viver",
    "nao aguento mais viver",
    "me machucar",
    "me cortar",
    "me ferir",
    "desistir de viver",
    # ideation phrasings that carry the topic word (accent-tolerant pairs)
    "penso em suicídio",
    "penso em suicidio",
    "pensando em suicídio",
    "pensando em suicidio",
    "pensado em suicídio",
    "pensado em suicidio",
    "me suicidar",
    "cometer suicídio",
    "cometer suicidio",
    "ideação suicida",
    "ideacao suicida",
]

# Topic-level mentions (the subject, not first-person intent). Checked only
# after needs_crisis_note() came back False.
SUICIDE_TOPIC_KEYWORDS = [
    "suicídio",
    "suicidio",
    "suicidar",
    "suicida",
]

CRISIS_NOTE = (
    "Se você está pensando em suicídio ou em se machucar, procure ajuda agora: "
    "o CVV — Centro de Valorização da Vida — oferece apoio emocional gratuito e "
    "sigiloso pelo telefone 188 (24 horas, todos os dias) e pelo chat em cvv.org.br. "
    "Em uma emergência, ligue 192 (SAMU)."
)

CRISIS_EXIT_MESSAGE = (
    "Sinto muito que você esteja passando por um momento tão difícil. Você não está "
    "só, e o que você sente importa. Antes de qualquer estudo, o mais importante "
    "agora é cuidar de você e falar com alguém agora mesmo.\n\n" + CRISIS_NOTE
)

_NO_ADVICE = """\
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria", \
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação, \
doação, separação, mudança de comportamento, ou qualquer outro curso de ação. \
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para \
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados.

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


def needs_medical_caveat(situation: str) -> bool:
    lower = situation.lower()
    return any(kw in lower for kw in CLINICAL_KEYWORDS)


def needs_crisis_note(text: str) -> bool:
    """First-person ideation/self-harm cues → the deterministic fixed exit."""
    lower = text.lower()
    return any(kw in lower for kw in CRISIS_KEYWORDS)


def mentions_suicide_topic(text: str) -> bool:
    """Topic-level mention of suicide (doctrinal question, grief about someone
    else). Callers must check needs_crisis_note() FIRST — this path answers
    normally and deterministically appends CRISIS_NOTE in code."""
    lower = text.lower()
    return any(kw in lower for kw in SUICIDE_TOPIC_KEYWORDS)


def _format_passages(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma passagem encontrada)"
    parts = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = f"[{i}] {m['book']}"
        if has_real_item_number(m.get("item_number")):
            header += f" | Item {m['item_number']}"
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
