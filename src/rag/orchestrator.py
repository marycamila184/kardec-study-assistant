import json
import logging
import re

from src.core.config import settings
from src.rag.llm_client import get_client
from src.rag.mode_detector import is_smalltalk
from src.rag.reflect_prompt import needs_crisis_note

logger = logging.getLogger(__name__)

_VALID_MODES = {"tirar_duvida", "refletir", "estudar_obra"}

_SYSTEM_PROMPT = (
    "Você é um roteador de intenção para um assistente de estudo das obras de "
    "Allan Kardec. Classifique a MENSAGEM do usuário em um destes modos:\n"
    '- "tirar_duvida": pergunta objetiva sobre a doutrina espírita ou sobre o '
    'conteúdo das obras (ex.: "o que é o perispírito?").\n'
    '- "refletir": a pessoa compartilha um sentimento, sofrimento ou situação '
    'pessoal e busca acolhimento (ex.: "estou muito mal, me ajuda").\n'
    '- "estudar_obra": a pessoa quer estudar um item/questão específico de uma '
    'obra (ex.: "explique a questão 132", "item 45 do Evangelho").\n'
    '- "nenhum": não se encaixa claramente em nenhum modo.\n'
    'Responda APENAS com JSON: {"mode": "<modo>", "confidence": "high"|"low"}. '
    'Use "high" apenas quando tiver certeza.'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(raw: str) -> dict:
    match = _JSON_RE.search(raw or "")
    if not match:
        return {"mode": None, "confidence": "low"}
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {"mode": None, "confidence": "low"}
    mode = data.get("mode")
    if mode not in _VALID_MODES:
        mode = None
    confidence = data.get("confidence", "low")
    return {"mode": mode, "confidence": confidence}


def classify_intent(
    message: str, current_mode: str | None, history: list[dict] | None = None
) -> dict:
    """Classify a free-text message into the mode that best fits it, for a
    non-destructive nudge button. Returns {"mode": <target|None>, "confidence":
    "high"|"low"}. Never nudges toward current_mode, on crisis/small-talk, on low
    confidence, or on any failure — deterministic safety runs before any LLM."""
    if not message or needs_crisis_note(message) or is_smalltalk(message):
        return {"mode": None, "confidence": "high"}
    try:
        response = get_client().chat.completions.create(
            model=settings.condenser_model,
            max_tokens=60,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        )
        result = _parse(response.choices[0].message.content)
    except Exception:
        logger.exception("classify_intent failed; returning no nudge")
        return {"mode": None, "confidence": "low"}
    if result["confidence"] != "high" or result["mode"] == current_mode:
        return {"mode": None, "confidence": result["confidence"]}
    return result
