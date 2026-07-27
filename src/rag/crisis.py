"""Deterministic crisis handling: first-person ideation exits, topic mentions
get the CVV note appended.

This layer lived in reflect_prompt.py because Refletir was where it was first
needed, but it never belonged to that mode — /chat and the orchestrator import
it too. It was moved out when Refletir was switched off, so that turning a mode
off can never turn the safety floor off with it.
"""

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
