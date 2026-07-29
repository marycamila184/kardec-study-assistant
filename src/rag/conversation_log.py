"""Anonymous per-turn logging, so answer quality can be judged from real use.

Design constraint, decided 2026-07-27 and RELAXED — only under consent — on
2026-07-28: without consent, nothing here may allow reconstructing one person's
session. An identifier is not only a name or an email; a random session id would
be pseudonymisation, not anonymisation, and it is exactly what lets "perdi meu
pai" + "moro em Belém" + "sou enfermeira" be joined back into a person. So by
default turns are still logged loose, with no linking id and without the history
that would rebuild the thread anyway.

`session_id` is written only when the caller passes one, which happens only when
the reader opted in through the banner (the frontend sends `X-Session-Id`; its
absence IS the refusal). This module never generates a session id and never
derives one from anything — see
docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md.

Two categories are sensitive under the LGPD and both apply to this app:
religious conviction (an app about Kardec logs it by nature) and health — which
is why `crise` and `abalo` turns record that the level happened and not one word
of what the person wrote.

Full reasoning: docs/superpowers/specs/2026-07-27-log-de-conversas-design.md
"""

import json
import logging
import re
import sys
import uuid

# Levels whose text is never recorded. `crise` means someone wrote about wanting
# to die; `abalo` means distress. Both are health data, the strictest category
# there is. The cost is real and accepted: crisis detection cannot be audited
# against real messages, only against the synthetic phrases in the tests and in
# probe_backend.py.
_TEXT_FREE_LEVELS = {"crise", "abalo"}

# Direct identifiers people type into free text. Coverage is imperfect by
# nature — this is proportionality, not a guarantee.
_SCRUBBERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[cep]"),
    (
        re.compile(r"(?<!\d)(?:\+55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)"),
        "[fone]",
    ),
]


def _make_logger() -> logging.Logger:
    """Emits the message and nothing else.

    uvicorn's default format prefixes `INFO:module:`, which would stop Cloud
    Logging from parsing the line as JSON — every turn would land as loose text
    instead of a queryable object.
    """
    logger = logging.getLogger("conversation")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


_logger = _make_logger()


def scrub(text: str) -> str:
    for pattern, replacement in _SCRUBBERS:
        text = pattern.sub(replacement, text)
    return text


def log_chat_turn(
    question: str,
    result: dict,
    latency_ms: int,
    suggested_mode: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> str:
    """One JSON line per turn. Never raises: observability must not be able to
    break an answer that already worked.

    Returns the turn_id on the line, so the route can hand the same id to the
    client without generating a second one. Generated OUTSIDE the try: even if
    logging fails, the route still needs an id to return.

    `session_id` arrives only when the reader consented — see
    docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md. This
    function never invents one.
    """
    turn_id = turn_id or str(uuid.uuid4())
    try:
        level = result.get("safety_level", "normal")
        sources = result.get("sources") or []
        payload: dict = {
            "event": "chat_turn",
            "severity": "INFO",
            "turn_id": turn_id,
            "n_sources": len(sources),
            "sources": [
                {
                    "book": s.get("book"),
                    "chapter": s.get("chapter_title") or s.get("chapter"),
                    "item": s.get("item_number"),
                }
                for s in sources
            ],
            "safety_level": level,
            "not_found": bool(result.get("not_found")),
            "generation_failed": bool(result.get("generation_failed")),
            "n_chips": len(result.get("suggested_questions") or []),
            "suggested_mode": suggested_mode,
            "latency_ms": latency_ms,
        }
        # Absent, not null. A null would read as "session unknown" and invite
        # queries to treat it as a field that is meant to be there; an empty
        # string is a header that arrived blank, which is refusal, not a
        # session named "".
        if session_id:
            payload["session_id"] = session_id
        # Absent, not empty: a null or "" would read as "there was no question",
        # and any future query would treat the field as present-but-blank.
        if level not in _TEXT_FREE_LEVELS:
            payload["question"] = scrub(question)
            payload["answer"] = scrub(result.get("answer", ""))
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - logging must never break a good answer
        logging.getLogger(__name__).exception("conversation logging failed")
    return turn_id
