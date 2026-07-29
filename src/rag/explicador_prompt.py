import json
import re

from src.rag.json_extract import extract_outermost, strip_code_fence
from src.rag.markers import parse_sections, split_pipe_list
from src.rag.profile import STUDY_DEFAULT, ResponseProfile, render_instructions
from src.rag.prompt_files import load
from src.rag.retriever import item_word

_MARKER_FORMAT = """\
REGRA ABSOLUTA DE FORMATO: responda usando EXATAMENTE estas duas seções, cada \
uma começando no início de uma linha, em MAIÚSCULAS, e nada mais — nenhum \
preâmbulo, nenhum markdown, nenhuma observação final.

CONTEXTO: <4 a 8 frases indicando onde este item se encaixa na estrutura da \
doutrina e, quando relevante, o contexto histórico/cultural em que foi dito>
CONCEITOS: <termo: definição> | <termo: definição>

Escreva de 1 a 3 conceitos, separados por " | ". Nunca escreva números de \
questão, de item ou de capítulo, nem referências no formato de citação — o \
sistema adiciona a citação depois, fora da sua resposta."""

# The rules below were duplicated verbatim across the JSON and marker templates.
# They had already drifted (the marker copy still quoted the JSON key
# `"contexto"`), and worse, the marker copy contradicted its own format rule:
# _MARKER_FORMAT forbids writing a work's name while the connection rule asked
# for "Esta ideia aparece também em...", which cannot be written without naming
# one. A model given both must violate one to satisfy the other — a plausible
# contributor to riv-ai-v2's 3/3 marker-protocol failure on 2026-07-25.
#
# Resolved in favour of the code-owned citation, which is the project's standing
# rule: the connection is described by its CONTENT, never by its reference. The
# reference already reaches the reader through the Curador's related_items cards.
_SHARED_RULES = load("study-rules")

_JSON_RULES = _SHARED_RULES.format(ctx='"contexto"', con='"conceitos_chave"')

# The inline grounding marker. Isolated as one constant so a prompt restructure
# can replace the wording wholesale: everything downstream depends on the marker
# SHAPE ("[item N]"), parsed in inline_refs.py, never on this sentence.
# An item not listed in [COMENTÁRIO DOUTRINÁRIO DESTE CAPÍTULO] is dropped in
# code, so a marker invented here costs the reference, not the reader's trust.
# See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
_ITEM_MARKER_RULE = load("study-item-marker")
_MARKER_RULES = _SHARED_RULES.format(ctx="CONTEXTO", con="CONCEITOS")

_SYSTEM_TEMPLATE = (
    load("study-system")
    + "\n\n"
    + _JSON_RULES
    + """

"""
    + _ITEM_MARKER_RULE
    + """

[TRECHO PRINCIPAL]
{main_passage}

[NOTAS DE RODAPÉ]
{footnote_passages}

[COMENTÁRIO DOUTRINÁRIO DESTE CAPÍTULO]
{chapter_commentary}

[REFERÊNCIAS RELACIONADAS]
{related_passages}"""
)

_MARKER_SYSTEM_TEMPLATE = (
    """\
Você é um tutor socrático especializado na obra de Allan Kardec.

"""
    + _MARKER_FORMAT
    + """

"""
    + _MARKER_RULES
    + """

[TRECHO PRINCIPAL]
{main_passage}

[NOTAS DE RODAPÉ]
{footnote_passages}

[COMENTÁRIO DOUTRINÁRIO DESTE CAPÍTULO]
{chapter_commentary}

[REFERÊNCIAS RELACIONADAS]
{related_passages}"""
)


def _format_related(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma)"
    parts = []
    for c in chunks:
        m = c["metadata"]
        parts.append(
            f"[{m['book']} | {item_word(m['book'])} {m['item_number']}]\n\"{c['content']}\""
        )
    return "\n\n".join(parts)


def build_explicador_messages(
    main_text: str,
    related_chunks: list[dict],
    footnote_context: str = "",
    chapter_commentary_chunks: list[dict] | None = None,
    markers: bool = False,
    profile: ResponseProfile = STUDY_DEFAULT,
) -> tuple[str, list[dict]]:
    template = _MARKER_SYSTEM_TEMPLATE if markers else _SYSTEM_TEMPLATE
    system = template.format(
        main_passage=main_text,
        footnote_passages=footnote_context or "(nenhuma)",
        chapter_commentary=_format_related(chapter_commentary_chunks or []),
        related_passages=_format_related(related_chunks),
    )
    # Appended, so an empty fragment leaves the prompt byte-identical. It lands
    # after the format rules on purpose: the JSON contract above is absolute and
    # nothing a profile says may read as loosening it.
    instructions = render_instructions(profile)
    if instructions:
        system += "\n\n" + instructions
    messages = [
        {"role": "user", "content": "Analise o trecho acima de forma socrática."}
    ]
    return system, messages


def _fix_conceitos_array(s: str) -> str:
    """Fix LLM habit of writing "term": "def" pairs inside the conceitos_chave array.

    Example of malformed input:
        "conceitos_chave": ["dever": "obrigação...", "lei": "regra..."]
    Becomes:
        "conceitos_chave": ["dever: obrigação...", "lei: regra..."]
    """

    def _replacer(m: re.Match) -> str:
        fixed = re.sub(r'"([^"]+)":\s*"([^"]+)"', r'"\1: \2"', m.group(2))
        return m.group(1) + fixed + m.group(3)

    return re.sub(
        r'("conceitos_chave"\s*:\s*\[)(.*?)(\])',
        _replacer,
        s,
        flags=re.DOTALL,
    )


def parse_explicador_json(text: str) -> tuple[str, list[str], list[str]]:
    """Returns (contexto, conceitos_chave, perguntas)."""
    text = strip_code_fence(text)

    def _try_parse(s: str):
        data = json.loads(s)
        conceitos = data.get("conceitos_chave", [])
        # Handle case where LLM returned a list of objects instead of strings
        if conceitos and isinstance(conceitos[0], dict):
            conceitos = [f"{k}: {v}" for item in conceitos for k, v in item.items()]
        return (
            data.get("contexto", ""),
            conceitos,
            data.get("perguntas", []),
        )

    def _find_and_parse(s: str):
        try:
            return _try_parse(s)
        except (json.JSONDecodeError, AttributeError, ValueError):
            pass
        block = extract_outermost(s, "{", "}")
        if block is not None:
            try:
                return _try_parse(block)
            except (json.JSONDecodeError, AttributeError, ValueError):
                pass
        return None

    # Try with the malformed-array fix first, then raw text
    for candidate in [_fix_conceitos_array(text), text]:
        result = _find_and_parse(candidate)
        if result is not None:
            return result

    # Regex extraction fallback — never show raw JSON to the user
    contexto_m = re.search(r'"contexto"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    perguntas_m = re.findall(r'"((?:[^"\\]|\\.){30,}\?)"', text)
    contexto = contexto_m.group(1).replace('\\"', '"') if contexto_m else ""
    perguntas = [p.replace('\\"', '"') for p in perguntas_m[:3]]
    return contexto, [], perguntas


def parse_explicador_markers(text: str) -> tuple[str, list[str], list[str]]:
    """Returns (contexto, conceitos_chave, perguntas) from marker output.

    `perguntas` is always [] — the field was removed from the prompt but is
    kept in the return shape so callers and the API schema are unchanged.

    Raises ValueError when no marker is present, so the caller treats it as a
    generation failure instead of leaking raw model text to the user.
    """
    sections = parse_sections(text, ["CONTEXTO", "CONCEITOS"])
    if not sections["CONTEXTO"] and not sections["CONCEITOS"]:
        raise ValueError("could not parse explicador marker response")
    return (
        sections["CONTEXTO"],
        split_pipe_list(sections["CONCEITOS"], limit=3),
        [],
    )
