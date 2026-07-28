"""Reads a message for a request about the SHAPE of the answer.

"traga as citações no texto" is not a doctrinal question — it is an instruction
about how to answer the doctrinal questions. Today the model sometimes honours
it by disobeying the prompt rule that forbids references in prose, which means
the reader's request works by accident and only until it doesn't.

Unlike classify_intent and classify_sensitivity, this one cannot run
concurrently with generation: its output shapes the prompt, so it has to finish
first. That is real serial latency on every turn, and the mitigations are the
ones available — a short prompt, a small model, a tight cap, and degrading to
"nothing changed" rather than making anyone wait.

**A dimension the reader asked for is pinned.** It stops following anything the
system infers later, so a conversation that lightens does not quietly take back
the citations someone asked for. Nothing here un-pins: only another explicit
request changes a pinned dimension.

See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md
"""

import dataclasses
import json
import logging
import re

from src.core.config import settings
from src.rag.llm_client import create_json_completion, get_client
from src.rag.profile import ResponseProfile

logger = logging.getLogger(__name__)

# Only the dimensions this slice renders. Adding one here without teaching
# render_instructions about it would let the classifier set something that
# changes nothing — a setting that silently does not work is worse than one
# that does not exist.
_CITATION_STYLE = {"none", "chips", "inline"}
_CITATION_PRECISION = {"short", "full"}

_SYSTEM_PROMPT = (
    "Você identifica se a MENSAGEM pede algo sobre a FORMA da resposta, e não "
    "sobre a doutrina. Responda APENAS com JSON.\n\n"
    "Campos possíveis (omita o que a mensagem não pedir):\n"
    '- "citacao": "inline" quando pedirem as citações dentro do texto '
    '(ex.: "traga as citações", "cite os trechos", "quero as passagens no '
    'texto"); "chips" quando pedirem as citações só ao lado ou de forma mais '
    'limpa; "none" quando pedirem para não citar.\n'
    '- "referencia": "full" quando pedirem a referência completa (obra, '
    'capítulo e item), ex.: "com a referência completa", "preciso citar em '
    'aula"; "short" quando pedirem referência curta.\n\n'
    "Uma pergunta comum sobre a doutrina não pede nada disso: responda {}.\n"
    'Exemplos: "o que é o perispírito?" -> {}. '
    '"traga as citações" -> {"citacao": "inline"}. '
    '"pode me dar a referência completa pra usar na aula?" -> '
    '{"citacao": "inline", "referencia": "full"}.'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def detect_profile_changes(message: str, profile: ResponseProfile) -> ResponseProfile:
    """Returns `profile` with any dimension the message asked for applied and
    pinned. Returns it unchanged on empty text or any LLM/parse failure — a
    classifier that cannot answer must never silently reshape someone's answer.
    """
    if not message:
        return profile

    try:
        response = create_json_completion(
            get_client(),
            model=settings.resolved_condenser_model,
            max_tokens=60,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        )
        raw = response.choices[0].message.content
        match = _JSON_RE.search(raw or "")
        if not match:
            return profile
        asked = json.loads(match.group(0))
    except Exception:
        logger.exception("detect_profile_changes failed; profile unchanged")
        return profile

    return apply_changes(profile, asked)


def apply_changes(profile: ResponseProfile, asked: dict) -> ResponseProfile:
    """The pure half, so the pinning rules are testable without a provider."""
    changes: dict = {}
    pinned = set(profile.pinned)

    style = asked.get("citacao")
    if style in _CITATION_STYLE and style != profile.citation_style:
        changes["citation_style"] = style
        pinned.add("citation_style")

    precision = asked.get("referencia")
    if precision in _CITATION_PRECISION and precision != profile.citation_precision:
        changes["citation_precision"] = precision
        pinned.add("citation_precision")

    if not changes:
        return profile

    logger.info("profile changed by request: %s", sorted(changes))
    return dataclasses.replace(profile, **changes, pinned=frozenset(pinned))
