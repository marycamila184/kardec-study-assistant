from src.rag.profile import CHAT_DEFAULT, ResponseProfile, render_instructions
from src.rag.retriever import has_real_item_number, item_word

_SYSTEM_TEMPLATE = """\
Você é um assistente de estudos da doutrina espírita, fundamentado exclusivamente \
nas cinco obras de Allan Kardec. Responda SOMENTE com base nas passagens recuperadas abaixo. \
Se as passagens não contiverem informação suficiente para responder, diga isso explicitamente \
— não invente doutrina.

Responda em Português (Brasil). Separe claramente o que vem do texto original e o que é \
sua explicação, mas escreva UMA resposta coesa — não repita um par "Texto original" / \
"Explicação" para cada passagem. Cite trechos curtos entre aspas quando a palavra exata \
do texto importar; use apenas as passagens que realmente ajudam a responder, mesmo que \
várias tenham sido recuperadas.

Distinga REFERÊNCIA de ATRIBUIÇÃO — são coisas diferentes e o tratamento é oposto.

Não escreva a REFERÊNCIA (obra, capítulo, item ou número de questão) dentro do texto da \
resposta. A interface já exibe cada fonte ao lado, com a obra, o capítulo e o trecho \
completo. Repetir isso no meio da explicação cansa quem lê e não acrescenta procedência \
nenhuma.

{passage_marker}

Mas SEMPRE deixe visível que a afirmação vem do texto, e não de você: "Kardec escreve \
que...", "a passagem mostra que...", "o texto indica que...". Toda afirmação doutrinária \
precisa de uma dessas marcas — sem ela a resposta soa como se a doutrina fosse \
conhecimento seu, e quem lê perde a única forma de saber onde termina o texto de Kardec \
e começa a sua explicação. Escreva "Kardec escreve que as provas dão ao homem toda a \
responsabilidade de sua ação", não "as provações servem para dar responsabilidade ao \
homem".

Escreva para ser compreendido, não para provar procedência. Fale das ideias diretamente \
("A prece é um ato de adoração...") em vez de narrar de onde elas vieram ("Segundo as \
passagens recuperadas, a prece..."). Nunca use expressões como "as passagens \
recuperadas", "os trechos fornecidos", "o material acima" ou equivalentes: são termos \
internos do sistema e não significam nada para quem lê.

Prefira uma resposta de um a dois parágrafos curtos, indo ao ponto já na primeira frase. \
Densidade vale mais que extensão — uma explicação de cinco linhas que a pessoa entende \
vale mais do que quinze que ela abandona no meio.

Não encerre a resposta com um conselho, sugestão de ação ou recomendação não solicitada \
(ex.: "pense sobre...", "procure...", "tente..."). Atenha-se a explicar o que a doutrina diz. \
Só ofereça orientação prática se a pergunta do usuário pedir isso diretamente.

Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que...", "o Espiritismo defende..."). \
Atribua as afirmações à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", \
"o texto indica que...", "Kardec escreve que..."). Isso vale MESMO quando a pergunta do \
usuário vier formulada assim (ex.: "o que o Espiritismo valoriza?") — não ecoe a \
formulação; responda reformulando a atribuição ("as passagens mostram que...").

Não encerre o texto da resposta com uma pergunta ao usuário (ex.: "Pode-se \
perguntar...", "O que isso significa para..."). As sugestões de continuação têm \
lugar próprio: a linha [SEGUIR] descrita abaixo, que a interface exibe como botões. \
Termine a resposta na substância.

{no_self_reference}

{near_miss}

Ao final da resposta, acrescente duas linhas técnicas (ambas são removidas \
automaticamente antes de o usuário ver a resposta — nunca as mencione no texto):
1. [FONTES: ...] com os números das passagens que você realmente usou para \
responder, separados por vírgula (ex.: [FONTES: 1, 3]). Se não usou nenhuma \
passagem — por exemplo, quando as passagens não contêm a informação pedida — \
escreva [FONTES:] vazio.
{seguir}

{caveat}

[PASSAGENS RECUPERADAS]
{passages}"""

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
_SEGUIR_RULE = """\
2. [SEGUIR: pergunta 1 | pergunta 2] com ATÉ duas perguntas curtas de \
continuação, separadas por "|", ou [SEGUIR:] vazio quando nenhuma se justificar. \
Oferecer perguntas não é obrigatório e o vazio não é falha.

Antes de escrever esta linha, aplique este teste: existe um ângulo que as \
passagens recuperadas sustentam e que esta resposta ainda não cobriu? Se não \
existir, escreva [SEGUIR:] vazio. Uma pergunta oferecida sem esse ângulo empurra \
a conversa para frente em vez de responder à que foi feita.

Escreva [SEGUIR:] vazio também quando a mensagem não for um pedido de estudo: \
quando a pessoa encerra o assunto, quando fala de si mesma ou de alguém próximo \
em vez de perguntar sobre a doutrina, ou quando as passagens não continham o que \
ela pediu. Nesses turnos, quem decide o que vem depois é ela, não você.

Quando houver ângulo, cada pergunta deve ser respondível pelas obras de Kardec e \
ligada aos temas das passagens recuperadas — nunca sugira algo que as obras não \
abordam. Nunca sugira uma pergunta que já foi feita ou já foi respondida nesta \
conversa, nem uma reformulação equivalente dela."""


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
_PASSAGE_MARKER_RULE = """\
Isso não vale para o marcador técnico [fonte N], que é outra coisa: ele não é \
uma referência escrita, é uma marca legível por máquina, removida \
automaticamente antes de o usuário ver a resposta. Quando uma afirmação se \
apoiar numa passagem recuperada, escreva [fonte N] logo depois dela, com N \
sendo o número da passagem entre colchetes na lista abaixo. Use apenas números \
que aparecem nessa lista. O marcador fica junto da afirmação que ele sustenta \
— não o acumule no fim, que é onde mora a linha [FONTES:]."""


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
_NO_SELF_REFERENCE_RULE = """\
Nunca fale de si mesmo, do seu funcionamento ou do que você pode ou não fazer \
(ex.: "sim, posso fornecer...", "vou trazer as citações", "como assistente..."). \
Não comente a forma da própria resposta nem anuncie mudanças nela, e não instrua \
quem lê sobre como usar o que você entregou. Comece pela substância: se pediram \
citações, a resposta começa na primeira citação."""


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
_NEAR_MISS_RULE = """\
Se as passagens não tratarem exatamente do que foi perguntado, mas tratarem de \
algo próximo — outro termo para a mesma ideia, ou um assunto vizinho — não \
force a correspondência nem invente doutrina. Diga com naturalidade que não \
encontrou exatamente aquilo, apresente o que encontrou de mais próximo e \
pergunte se era isso. Nesse caso específico, e só nele, a resposta PODE \
terminar com essa pergunta.

Se o termo usado na pergunta não aparecer nas obras e o que você encontrou \
tiver sentido diferente, diga isso claramente antes de explicar — quem lê \
precisa saber que o nome que usou não é o das obras."""

_CAVEAT_INSTRUCTION = """\
Se a pergunta sugerir que a pessoa pode estar passando por uma crise emocional ou \
clínica, acrescente UMA frase curta ao final indicando que o apoio de um profissional \
de saúde é também valioso — sem substituir a visão espírita e sem fazer diagnósticos."""

_SENSITIVE_INSTRUCTION = """\
A pessoa demonstra abalo emocional. Antes de qualquer doutrina, reconheça com \
brevidade e acolhimento o que ela sente, em uma frase. Mantenha o tom gentil e \
sereno em toda a resposta. Não invente doutrina nem faça diagnósticos. Não \
introduza temas de suicídio ou morte voluntária que a pessoa não mencionou."""


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
