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

from src.core.config import settings

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
    mode: str = "chat",
    n_history: int = 0,
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
            "mode": mode,
            # How many previous turns the client sent, never one word of them.
            # Rule nº2 of 2026-07-27 is about the content: a count cannot
            # rebuild a conversation.
            "n_history": n_history,
            # The lane that actually wrote the prose, which is not always the
            # one that answers structured JSON. With PROSE_PROVIDER unset the
            # two coincide; when they do not, the log has to say who answered —
            # that is the whole point of the field. A missing CHAT_MODEL once
            # cost a deploy with every /chat returning 503.
            "model": settings.resolved_prose_model,
            "provider": settings.prose_provider_name,
            # Everything retrieval returned, not just what was cited. `sources`
            # below is the cited subset.
            "retrieved": result.get("retrieved") or [],
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
            # What the model wrote when the quote guard withheld the answer.
            # Under the same tier gate as everything else textual: `crise` and
            # `abalo` record no text, and consent does not unlock them.
            # Absent, not null, when nothing was withheld — the same rule the
            # session id follows, so a query can tell "not withheld" from
            # "withheld and blank".
            withheld = result.get("withheld_answer")
            if withheld:
                payload["withheld_answer"] = scrub(withheld)
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - logging must never break a good answer
        logging.getLogger(__name__).exception("conversation logging failed")
    return turn_id


def log_feedback(turn_id: str, vote: str, session_id: str | None = None) -> None:
    """A thumbs up or down, joined to its turn by `turn_id` at query time.

    Same stdout, same sink, no new storage and no network I/O on the response
    path. Never raises, like everything else here.

    The vote carries no text by design: a free-text field would reopen the
    whole sensitive-data question the spec settled.
    """
    try:
        payload: dict = {
            "event": "feedback",
            "severity": "INFO",
            "turn_id": turn_id,
            "vote": vote,
        }
        if session_id:
            payload["session_id"] = session_id
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - logging must never break a good answer
        logging.getLogger(__name__).exception("feedback logging failed")


def log_study_turn(
    book: str,
    item_number: str,
    chapter: str | None,
    result: dict,
    latency_ms: int,
    session_id: str | None = None,
) -> str:
    """A studied item, on the same event as a chat turn.

    Same event name on purpose: reading quality should be one query, not a
    union of two. What differs is `mode`, and that `question` names the item
    studied — there is no typed question in a study.

    /study logged nothing at all until 2026-07-28, which is why the daily
    passage that motivated the spec left no trace to look at.
    """
    ref = " — ".join(filter(None, [book, chapter, f"item {item_number}"]))
    return log_chat_turn(
        ref,
        {
            "answer": result.get("contexto", ""),
            "sources": result.get("sources") or [],
            "not_found": False,
            "generation_failed": bool(result.get("generation_failed")),
            "suggested_questions": [],
            "safety_level": "normal",
            "retrieved": result.get("retrieved") or [],
        },
        latency_ms=latency_ms,
        session_id=session_id,
        mode="study",
    )
