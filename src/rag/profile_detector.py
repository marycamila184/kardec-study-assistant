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
    '- "nivel": "leve" quando a mensagem for simples, curta ou de quem está '
    'começando; "denso" quando for elaborada, técnica, ou usar termos da '
    'doutrina com familiaridade; "medio" no caso comum. Sempre responda este '
    "campo.\n\n"
    'Só preencha "citacao" e "referencia" quando a mensagem der uma '
    "INSTRUÇÃO sobre a forma da resposta. Perguntar o que Kardec diz, o que uma "
    "obra ensina ou pedir explicação NÃO é pedir citação — é a pergunta comum, "
    'e a resposta é apenas {"nivel": "..."}.\n'
    'Exemplos: "o que é o perispírito?" -> {"nivel": "medio"}. '
    '"o que Kardec diz sobre a prece?" -> {"nivel": "medio"} '
    "(pergunta sobre a doutrina, não pedido de citação). "
    '"traga as citações" -> {"citacao": "inline", "nivel": "medio"}. '
    '"o que acontece quando a gente morre?" -> {"nivel": "leve"}. '
    '"como a lei de afinidade opera na erraticidade?" -> {"nivel": "denso"}.'
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

    updated = apply_changes(profile, asked)
    level = _LEVEL_NAMES.get(asked.get("nivel"))
    if level is not None:
        updated = apply_level(updated, level)
    return updated


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


# The inferred level, and the only thing the classifier estimates on its own.
#
# One reading — how dense this conversation has become — fills two dimensions at
# once with values that cohere. Inferring depth and vocabulary independently
# would be two chances to be wrong and a combination nobody chose: "aprofundado
# + iniciante" is not a reader, it is a contradiction.
_LEVELS = (
    ("breve", "iniciante"),
    ("normal", "corrente"),
    ("aprofundado", "tecnico"),
)
_NEUTRAL_LEVEL = 1

_LEVEL_NAMES = {"leve": 0, "medio": 1, "denso": 2}


def current_level(profile: ResponseProfile) -> int:
    """Where the profile sits today, read back from its dimensions.

    Derived rather than stored: a `level` field could disagree with the depth
    and vocabulary it is supposed to describe, and then two things would claim
    to be the truth.
    """
    pair = (profile.depth, profile.vocabulary)
    for index, values in enumerate(_LEVELS):
        if pair == values:
            return index
    return _NEUTRAL_LEVEL


def apply_level(profile: ResponseProfile, target: int) -> ResponseProfile:
    """Moves the profile ONE step toward `target`, never further.

    One step at a time is what makes the change unnoticeable, which is the whole
    requirement: a jump from neutral to technical between two turns is exactly
    the seam this is meant not to have. It also means a single odd message
    cannot reshape a conversation — it takes a consistent direction to travel.

    A pinned dimension does not move. The reader asked for it, and an inference
    is not an argument against a request.
    """
    target = max(0, min(len(_LEVELS) - 1, target))
    now = current_level(profile)
    if target == now:
        return profile

    step = now + (1 if target > now else -1)
    depth, vocabulary = _LEVELS[step]

    changes = {}
    if "depth" not in profile.pinned:
        changes["depth"] = depth
    if "vocabulary" not in profile.pinned:
        changes["vocabulary"] = vocabulary
    if not changes:
        return profile

    logger.info("profile level %d -> %d", now, step)
    return dataclasses.replace(profile, **changes)
