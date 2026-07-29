"""The response profile: what shape an answer takes, separated from which route
produced it.

Response shape used to be a property of the endpoint — /study meant structured
JSON with conceitos-chave, /chat meant prose with source chips — so a reader who
wanted the citations inside the text had no way to ask. This module is the seam
that makes shape an input.

Two families, because they cost different things. The retrieval dimensions
change how much text reaches the prompt; the presentation dimensions change only
the surface.

What this module deliberately cannot touch: retrieval grounding, the visible
separation between source text and AI explanation, the crisis floor, and the
rule against personifying "o Espiritismo". Those are enforced in code elsewhere
and no profile value reaches them. A profile decides how an answer looks, never
whether it is accountable for what it says.

See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md
"""

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class ResponseProfile:
    """A value, not a setting. Frozen because a shared mutable default would let
    one request's shape leak into the next — a bug invisible until a confused
    reader reports it.

    Use `replace(profile, depth="aprofundado")` to derive a variant.
    """

    # ── Retrieval: changes what reaches the prompt ────────────────────────────
    # single item | item within its chapter | the whole chapter
    chapter_coverage: str = "item"
    # obras | obras_historico | historico
    scope: str = "obras_historico"

    # ── Presentation: changes only the surface ────────────────────────────────
    citation_style: str = "chips"  # none | chips | inline
    citation_precision: str = "short"  # short | full
    depth: str = "normal"  # breve | normal | aprofundado
    vocabulary: str = "corrente"  # iniciante | corrente | tecnico
    answer_format: str = "prosa"  # prosa | topicos | estruturado
    quote_density: str = "normal"  # baixa | normal | alta — never zero
    sections: frozenset = frozenset()
    study_scaffolding: bool = False
    # The long tail not yet mapped. Size-capped and kept away from the part of
    # the system prompt carrying the invariants — it is the obvious injection
    # surface, and "ignore as fontes" must not work.
    extra: str = ""

    # Dimensions the reader asked for explicitly. They stop following anything
    # inferred later, so a conversation that lightens does not quietly take back
    # citations someone asked for. The system never un-pins; only another
    # explicit request changes a pinned dimension.
    pinned: frozenset = frozenset()


EXTRA_MAX_CHARS = 500

# The presets reproduce today's behaviour exactly. Their field values document
# what each mode already does; they do not yet cause it.
CHAT_DEFAULT = ResponseProfile(
    sections=frozenset({"seguir"}),
)

# Someone who opened Estudar has already said what they came for, so that mode
# does not start at the neutral depth a first question in Dialogar gets.
# Reported 2026-07-28: first answers there read as too short, because the level
# starts neutral and only climbs a step per turn.
#
# `depth` is PINNED, and the reason is mechanical as well as semantic: a profile
# at aprofundado/corrente matches none of the paired levels, so the classifier
# would read it as neutral and could pull it back down on the next turn.
# Choosing the mode is an explicit act, and an explicit request still overrides
# a pin — "explique mais simples" works exactly as it always did.
#
# Vocabulary stays `corrente`. Deep is not the same as technical, and someone
# new to the works can open Estudar; the product exists to lower that barrier.
MODE_DEFAULTS = {
    "estudar_obra": ResponseProfile(
        depth="aprofundado",
        # The passages in the text, not behind a chip. Measured on 2026-07-28:
        # inline took verbatim quotation from 2 to 12 across three questions.
        # A study screen is where someone came to read Kardec's words, so they
        # belong in front of them.
        #
        # `citation_precision` stays short on purpose: the full reference is for
        # copying a citation out of the app, which is a request, not a mode.
        citation_style="inline",
        sections=frozenset({"seguir"}),
        pinned=frozenset({"depth"}),
    ),
}

STUDY_DEFAULT = ResponseProfile(
    answer_format="estruturado",
    sections=frozenset({"conceitos", "perguntas", "relacionados", "chapter_context"}),
)


# One fragment per non-default value. A dimension sitting at its default
# renders nothing, because the base prompt already says what the default means —
# repeating it would only give the model a second, differently-worded copy of a
# rule it already has.
_CITATION_STYLE_FRAGMENTS = {
    "inline": (
        "Esta pessoa pediu as citações dentro do texto. Traga os trechos "
        "entre aspas ao longo da explicação, cada um seguido do marcador "
        "[fonte N] da passagem correspondente. A regra de não escrever "
        "referências em prosa continua valendo: quem exibe obra, capítulo e "
        "item é a interface, não você."
    ),
    "none": (
        "Esta pessoa pediu uma resposta sem citações. Explique com suas "
        "palavras, sem trechos entre aspas. Continue marcando o que vem do "
        "texto ('Kardec escreve que...'), continue escrevendo [fonte N] "
        "depois de cada afirmação que se apoia numa passagem, e continue "
        "escrevendo a linha [FONTES:] normalmente — o que muda é só o que "
        "aparece na tela, nunca o que sustenta a resposta."
    ),
}


# Depth and vocabulary are what the inferred level moves. Only the non-default
# values render: a conversation sitting at "normal/corrente" says nothing extra,
# which is what keeps the neutral prompt byte-identical.
_DEPTH_FRAGMENTS = {
    "breve": (
        "Responda em no máximo um parágrafo curto, com um trecho citado ou "
        "nenhum. Vá direto ao ponto doutrinário e pare — quem pergunta assim "
        "quer a resposta, não o percurso até ela."
    ),
    "aprofundado": (
        "Esta conversa já foi fundo. Desenvolva a explicação com mais "
        "detalhe, citando quantos trechos forem necessários e mostrando como "
        "o ponto se articula com outras passagens das obras. Continue sem "
        "inventar doutrina e sem sair das passagens."
    ),
}

_VOCABULARY_FRAGMENTS = {
    "iniciante": (
        "Quem pergunta está começando. Explique os termos da doutrina na "
        "primeira vez que aparecerem, em linguagem comum, sem supor leitura "
        "prévia das obras."
    ),
    "tecnico": (
        "Quem pergunta conhece a doutrina. Use os termos próprios sem "
        "explicá-los do zero e não simplifique o vocabulário."
    ),
}


def render_instructions(profile: ResponseProfile) -> str:
    """The prompt fragment expressing a profile.

    Empty for the presets, which is what keeps the seam provable: the assembled
    prompt is byte-identical to the pre-profile one until a dimension actually
    leaves its default.

    `citation_precision` is deliberately NOT here. Adding a fragment that
    contradicts a base rule does not work — the 2026-07-28 A/B measured zero
    prose references even in the lane asking for them, because the model obeyed
    the stronger, earlier rule. That dimension SUBSTITUTES the base rule in
    prompt.py instead, so the prompt says one thing at a time.
    """
    fragments = [
        _CITATION_STYLE_FRAGMENTS.get(profile.citation_style),
        _DEPTH_FRAGMENTS.get(profile.depth),
        _VOCABULARY_FRAGMENTS.get(profile.vocabulary),
    ]
    return "\n\n".join(f for f in fragments if f)
