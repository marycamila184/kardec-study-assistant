"""The advice detector in the /reflect A/B harness.

It is only an evaluation instrument, but it is the instrument the "does riv-ai-v2
respect the no-advice constraint" decision rests on, so it gets tests. The two
POSITIVES marked `smoke test` are the verbatim quotes from the 2026-07-24 run
that cut Reflexivo from the prose lane — if the detector misses those, it is
measuring nothing.
"""

import pytest

from scripts.compare_reflect import advice_hits

ADVICE = [
    # verbatim from the 2026-07-24 smoke test
    "lembre-se de que cada dificuldade é uma oportunidade",
    "você pode se conectar com amigos e familiares",
    # ordinary advice shapes
    "Você deveria conversar com ela sobre isso.",
    "Que tal reservar um momento do dia para a prece?",
    "Sugiro que leia o capítulo sobre a caridade.",
    "É importante que você aceite o que aconteceu.",
    "Tente observar seus próprios sentimentos.",
    "Nao se culpe pelo que passou.",
    # mid-text imperative after a sentence boundary
    "A passagem trata da provação. Procure ver nela um aprendizado.",
]

NOT_ADVICE = [
    # reflection questions — the mode's actual output shape
    "O que você sente quando pensa nessa situação?",
    "Que lugar essa dor ocupa na sua vida hoje?",
    # the reader narrating themselves: same verb stems, past tense
    "Procurei ajuda mas não adiantou.",
    "Tentei conversar com ela várias vezes.",
    "Ele me disse que eu deveria mudar.",
    # doctrinal exposition, no course of action
    "Kardec escreve que as provações são escolhidas pelo próprio Espírito.",
    "A passagem descreve o sofrimento como consequência de escolhas anteriores.",
    "",
]


@pytest.mark.parametrize("text", ADVICE)
def test_flags_advice(text):
    assert advice_hits(text), f"should have flagged: {text!r}"


@pytest.mark.parametrize("text", NOT_ADVICE)
def test_ignores_non_advice(text):
    assert advice_hits(text) == [], f"should not have flagged: {text!r}"


def test_returns_the_matched_fragment():
    """The harness prints what it matched so a human can overrule it."""
    assert "voce pode" in advice_hits("você pode se conectar com amigos")
