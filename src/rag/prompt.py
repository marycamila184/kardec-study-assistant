import re

from src.rag.profile import CHAT_DEFAULT, ResponseProfile, render_instructions
from src.rag.prompt_files import load
from src.rag.retriever import has_real_item_number, item_word

_SYSTEM_TEMPLATE = load("chat-system")

# Read from the module at call time by build_messages(), so an A/B variant is a
# single patch — same shape as reflect_prompt._NO_ADVICE, and for the same
# reason: comparing two versions of this rule by editing the file between runs
# is how you end up unable to tell a prompt effect from sampling noise.
#
# Stated as a TEST the model applies, not as "ofereça se achar útil". The
# _NO_ADVICE history in reflect_prompt.py is the evidence: a soft instruction
# gets complied with unevenly, and enumerating surface forms gets routed around
# one synonym away. Naming the condition — is there an angle the passages
# support that this answer has not covered — leaves nothing to route around.
_SEGUIR_RULE = load("chat-seguir")

_CAVEAT_INSTRUCTION = load("chat-caveat")

_SENSITIVE_INSTRUCTION = load("chat-sensitive")


_CAVEAT_HEADING = "# Cuidado com a pessoa"


def _collapse_blank_runs(text: str) -> str:
    """Three or more newlines become two — one blank line, never a gap.

    An empty `{slot}` leaves the blank line above it and the one below it
    touching. Markdown reads the result the same, but the prompt is assembled
    for a model, and a gap where a section used to be is one more thing it has
    to decide the meaning of. Runs at the seams only: nothing in these files
    uses a double blank line on purpose.
    """
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def _absent_terms_note(terms: list[str] | None) -> str:
    """Tells the model which words of the question the works never use.

    The signal is deterministic — checked against the corpus in
    premise_check.py — and the wording is left to the model, which is the
    division that keeps the answer conversational without letting it invent.
    A fixed sentence in code was tried first and read as a machine correcting
    the reader.

    Empty when there is nothing to say, so the neutral prompt is unchanged.
    """
    if not terms:
        return ""
    listed = ", ".join(f'"{t}"' for t in terms)
    return (
        f"AVISO: {listed} não aparece(m) em nenhuma das obras de Kardec. Diga "
        "isso a quem perguntou, com suas palavras, antes de explicar o que as "
        "passagens de fato trazem. Não trate esse termo como doutrina."
    )


def _format_passage(index: int, chunk: dict) -> str:
    """The header carries the CANONICAL reference, not just the chapter title.

    The two used to disagree: this header printed "Capítulo: OS FLUIDOS" while
    the source chip beside the answer printed "cap. XIV". A model can only echo
    what it is shown, so when a reader asked for citations in the text they got
    the title in the prose and the number in the chip — two references to the
    same passage, looking like two different places. For someone copying it into
    a class handout, that is the difference between a usable citation and a
    wrong one.
    """
    m = chunk["metadata"]
    header = f"[{index}] Obra: {m['book']}"
    chapter_ref, chapter_title = m.get("chapter"), m.get("chapter_title")
    if chapter_ref and chapter_title:
        header += f" | {chapter_ref} — {chapter_title}"
    elif chapter_title:
        header += f" | Capítulo: {chapter_title}"
    elif chapter_ref:
        header += f" | {chapter_ref}"
    if has_real_item_number(m.get("item_number")):
        header += f" | {item_word(m['book'])}: {m['item_number']}"
    return f"{header}\n    \"{chunk['content']}\""


def build_messages(
    question: str,
    chunks: list[dict],
    history: list[dict],
    max_history_turns: int = 10,
    add_caveat: bool = False,
    sensitive: bool = False,
    profile: ResponseProfile = CHAT_DEFAULT,
    absent_terms: list[str] | None = None,
) -> tuple[str, list[dict]]:
    passages = "\n\n".join(_format_passage(i + 1, c) for i, c in enumerate(chunks))
    notes = []
    if sensitive:
        notes.append(_SENSITIVE_INSTRUCTION)
    if add_caveat:
        notes.append(_CAVEAT_INSTRUCTION)
    system = _collapse_blank_runs(
        _SYSTEM_TEMPLATE.format(
            passages=passages,
            # The heading travels with the text it introduces. Left in the
            # template it outlived its content: `{caveat}` is empty on most
            # turns, so the COMMON prompt carried "# Cuidado com a pessoa"
            # followed by nothing, and the rare one was the clean one.
            caveat=(f"{_CAVEAT_HEADING}\n\n" + "\n\n".join(notes) if notes else ""),
            seguir=_SEGUIR_RULE,
            absent_terms=_absent_terms_note(absent_terms),
        )
    )
    # Appended rather than woven into the template so an empty fragment leaves
    # the prompt byte-identical. The sensitivity and caveat instructions above
    # keep their position: they are not presentation, and a profile must never
    # be able to displace them.
    instructions = render_instructions(profile)
    if instructions:
        system += "\n\n" + instructions

    messages = [
        {"role": t["role"], "content": t["content"]}
        for t in history[-max_history_turns:]
    ]
    messages.append({"role": "user", "content": question})

    return system, messages
