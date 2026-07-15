import json
import logging
import re

from src.core.config import settings
from src.rag.llm_client import get_client

logger = logging.getLogger(__name__)

_VALID_LEVELS = {"normal", "abalo", "crise"}

_SYSTEM_PROMPT = (
    "Você classifica a sensibilidade emocional da MENSAGEM de uma pessoa em um "
    "assistente de estudo espírita. Responda com um destes níveis:\n"
    '- "normal": pergunta comum, de estudo ou factual, sem sofrimento pessoal '
    'evidente (ex.: "o que é o perispírito?").\n'
    '- "abalo": a pessoa expressa sofrimento emocional, cansaço extremo, angústia '
    'ou desânimo, SEM sinal claro de suicídio ou autolesão (ex.: "estou muito mal", '
    '"não aguento mais", "cansada de tudo").\n'
    '- "crise": há sinal de ideação suicida ou de se machucar (ex.: "não quero mais '
    'viver", "queria sumir", "penso em me machucar").\n'
    "Na dúvida entre dois níveis, escolha o MAIS cuidadoso (crise > abalo > normal).\n"
    'Responda APENAS com JSON: {"nivel": "<nivel>"}.'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def classify_sensitivity(text: str) -> str:
    """Small-LLM classifier of a message's emotional sensitivity. Returns one of
    'normal' | 'abalo' | 'crise'. Defaults to 'normal' on empty text or any
    LLM/parse failure — safe because this signal only escalates handling; the
    deterministic keyword crisis floor is applied separately by the caller."""
    if not text:
        return "normal"
    try:
        response = get_client().chat.completions.create(
            model=settings.condenser_model,
            max_tokens=30,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        raw = response.choices[0].message.content
        match = _JSON_RE.search(raw or "")
        if not match:
            return "normal"
        level = json.loads(match.group(0)).get("nivel")
        return level if level in _VALID_LEVELS else "normal"
    except Exception:
        logger.exception("classify_sensitivity failed; defaulting to normal")
        return "normal"
