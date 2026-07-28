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


EXTRA_MAX_CHARS = 500

# The presets reproduce today's behaviour exactly. Their field values document
# what each mode already does; they do not yet cause it.
CHAT_DEFAULT = ResponseProfile(
    sections=frozenset({"seguir"}),
)

STUDY_DEFAULT = ResponseProfile(
    answer_format="estruturado",
    sections=frozenset({"conceitos", "perguntas", "relacionados", "chapter_context"}),
)


def render_instructions(profile: ResponseProfile) -> str:
    """The prompt fragment expressing a profile.

    Returns "" for every profile today, on purpose. The existing prompts already
    say what the neutral defaults mean, so an empty fragment reproduces them
    character for character — which is what makes this step provable: the seam
    is either completely inert or obviously broken, with nothing in between.

    Step 3 of the umbrella spec fills this in, one dimension at a time, each
    with a test that the fragment appears only when the dimension leaves its
    default.
    """
    return ""
