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


# The inline grounding marker.
#
# Worded to sit WITH the "Distinga REFERÊNCIA de ATRIBUIÇÃO" rule above, not
# against it: that rule forbids writing a human-readable reference (obra,
# capítulo, item) into the prose, because the interface already shows it. This
# marker is machine-readable and removed before display, so the two are not in
# conflict — but a marker prompt that reads as contradicting the reference rule
# is exactly how the /study marker contract failed once before, so the
# distinction is stated rather than assumed.
#
# Isolated as one constant so a prompt restructure can replace the wording
# wholesale: everything downstream depends on the marker SHAPE ("[fonte N]"),
# parsed in inline_refs.py, never on this sentence. An index outside the
# retrieved list is dropped in code.
# See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
_PASSAGE_MARKER_RULE = load("chat-passage-marker")


# The system does not talk about itself.
#
# Found in production on 2026-07-28. Asked for citations, the answer opened with
# "Sim, posso fornecer citações das obras de Allan Kardec... No entanto, é
# importante notar que as citações devem ser usadas para..." — the assistant
# describing what it can do and then lecturing the reader on how to use it.
#
# This belongs beside the personification rule as a constraint on voice, and it
# is what makes an adapting response feel like being understood rather than like
# a machine announcing a mode change: the prose simply arrives already shaped.
# Isolated as one constant so a prompt restructure can replace the wording.
_NO_SELF_REFERENCE_RULE = load("chat-no-self-reference")


# The near miss, handled in the answer instead of by a fixed note in code.
#
# A deterministic correction was tried first and read as a machine correcting
# the reader: every near miss got the same sentence, in the same words,
# regardless of how close the retrieved passages actually were. Judging "close
# enough" is the part a model does better than a word list, and the cost of
# being wrong here is a clumsy sentence rather than invented doctrine — the
# grounding rules above still hold either way.
#
# This is the ONE place the answer may end on a question. The rule against it
# exists so follow-ups live in [SEGUIR] as buttons; a "did you mean this?" is
# not a follow-up, it is the answer needing confirmation before it is useful.
# Stated as an exception rather than left to be inferred, because a rule that
# contradicts its neighbour gets obeyed unpredictably.
_NEAR_MISS_RULE = load("chat-near-miss")

_CAVEAT_INSTRUCTION = load("chat-caveat")

_SENSITIVE_INSTRUCTION = load("chat-sensitive")


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
    system = _SYSTEM_TEMPLATE.format(
        passages=passages,
        caveat="\n\n".join(notes),
        seguir=_SEGUIR_RULE,
        passage_marker=_PASSAGE_MARKER_RULE,
        no_self_reference=_NO_SELF_REFERENCE_RULE,
        near_miss=_NEAR_MISS_RULE,
        absent_terms=_absent_terms_note(absent_terms),
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
