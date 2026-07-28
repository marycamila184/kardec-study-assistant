import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from src.core.config import settings
from src.rag.citations import (
    extract_model_citations,
    retrieved_ids,
    strip_model_citations,
    validate_model_citations,
)
from src.rag.crisis import (
    CRISIS_EXIT_MESSAGE,
    CRISIS_NOTE,
    mentions_suicide_topic,
    needs_crisis_note,
    needs_medical_caveat,
)
from src.rag.groundedness import attribute_sources
from src.rag.guardrails import (
    counts_personification,
    strip_internal_terms,
    strip_trailing_question,
)
from src.rag.inline_refs import (
    InlineMarkerFilter,
    extract_passage_refs,
    render_references,
)
from src.rag.markers import strip_marker_debris, strip_trailing_markers
from src.rag.mode_detector import extract_study_reference, is_smalltalk
from src.rag.profile import CHAT_DEFAULT, ResponseProfile
from src.rag.prompt import build_messages
from src.rag.prose import prose_completion, prose_completion_stream
from src.rag.query_condenser import blend_anchor, condense_query
from src.rag.quote_check import StreamingQuoteGuard, find_unsupported_quotes
from src.rag.retriever import (
    EVANGELHO_BOOK,
    append_chapter_commentary,
    filter_sensitive_chunks,
    has_real_item_number,
    retrieve,
    retrieve_by_item,
)
from src.rag.sensitivity import classify_sensitivity
from src.rag.stream_buffer import StreamBuffer

logger = logging.getLogger(__name__)

_SENSITIVITY_TIMEOUT_S = 8.0

NOT_FOUND_MESSAGE = (
    "Não encontrei nas obras de Kardec passagens que respondam com segurança a essa "
    "pergunta — e prefiro não inventar doutrina. Tente perguntar com outras palavras: "
    "às vezes um termo diferente encontra o trecho certo. Se preferir navegar pelo "
    "texto, o modo Estudar uma Obra permite abrir qualquer questão diretamente."
)

BOOK_FALLBACK_NOTE = (
    "Não encontrei citações específicas sobre esse tema em *{book}*. "
    "Porém, outras obras de Kardec abordam o assunto:\n\n"
)

GENERATION_FAILED_MESSAGE = "Não foi possível gerar uma resposta agora. Por favor, tente novamente em instantes."

# Brief warm replies for pure acknowledgment / closing messages (see
# is_smalltalk). No retrieval, no LLM, no source chips — just a human closing.
SMALLTALK_REPLIES = (
    "De nada! Fico feliz em ajudar. 🙏",
    "Imagina! Estou por aqui sempre que surgir outra dúvida.",
    "Por nada! Que bom poder acompanhar seus estudos.",
    "De nada! Sempre que quiser aprofundar, é só chamar.",
)


class UnsupportedQuoteError(Exception):
    """The answer quoted something that is in no retrieved passage."""

    def __init__(self, quotes: list[str]) -> None:
        super().__init__("answer contains unsupported quotations")
        self.quotes = quotes


def _crisis_exit() -> dict:
    """Fixed, deterministic crisis response — no retrieval, no citations, no chips.
    Never depends on the generation LLM."""
    return {
        "answer": CRISIS_EXIT_MESSAGE,
        "sources": [],
        "suggested_questions": [],
        "not_found": False,
        "generation_failed": False,
        "safety_level": "crise",
    }


def _direct_item_chunks(question: str, book_filter: str | None) -> list[dict]:
    """Deterministic lookup for item-reference questions ("questão 132 do
    Livro dos Espíritos"). Semantic search can't reliably find an item by
    its number, so when the question names a specific item and the book is
    known (named in the question, or implied by an active book filter),
    fetch that item's chunks directly. Returns [] when not applicable."""
    ref = extract_study_reference(question)
    book = ref["book"] or book_filter
    if not (ref["item_number"] and book):
        return []
    if book == EVANGELHO_BOOK:
        # "item N do Evangelho" is ambiguous — item numbers repeat across ~28
        # chapters, so a chapterless direct lookup would return them all. Defer
        # to (enriched) semantic retrieval instead.
        return []
    try:
        return retrieve_by_item(book, ref["item_number"])
    except Exception:
        logger.exception("direct item lookup failed in /chat generate")
        return []


def _prepare(
    question: str,
    history: list[dict],
    book_filter: str | None = None,
    anchor_text: str | None = None,
    profile: ResponseProfile = CHAT_DEFAULT,
) -> tuple[dict | None, dict | None]:
    """Everything that happens before the model call: the short-circuits, the
    sensitivity tier, retrieval, and the prompt.

    Returns (early_result, context). Exactly one of the two is set: an
    early_result is a finished response that must be returned as-is — small
    talk, the crisis exit, a retrieval failure, no chunks — and it is what keeps
    those paths from ever opening a stream.
    """
    # A pure "obrigada / entendi / valeu" needs a warm closing, not a doctrinal
    # answer with source chips. Short-circuit before any retrieval or LLM call.
    if is_smalltalk(question) and not needs_crisis_note(question):
        return {
            "answer": random.choice(SMALLTALK_REPLIES),
            "sources": [],
            "suggested_questions": [],
            "not_found": False,
            "generation_failed": False,
            "safety_level": "normal",
        }, None

    # Deterministic crisis floor: a keyword hit short-circuits to the fixed exit
    # before any retrieval or classifier call — never gated on the LLM.
    if needs_crisis_note(question):
        return _crisis_exit(), None

    # Topic-level mention (no ideation — that exited above): answer normally,
    # but always carry the CVV note, appended in code before returning. The
    # sensitivity classifier can still escalate this turn to a full exit.
    topic_note = mentions_suicide_topic(question)

    # The sensitivity classifier runs concurrently with retrieval (both are
    # pre-generation), so it adds no serial latency in the common path.
    executor = ThreadPoolExecutor(max_workers=1)
    sensitivity_future = executor.submit(classify_sensitivity, question)
    try:
        search_query = question
        if history:
            try:
                search_query = condense_query(question, history)
            except Exception:
                logger.exception("condense_query failed in /chat; using raw question")
                search_query = question

        search_query = blend_anchor(search_query, anchor_text)

        direct_chunks = _direct_item_chunks(question, book_filter)

        try:
            chunks = retrieve(search_query, book_filter=book_filter)
        except Exception:
            logger.exception("retrieve failed in /chat generate")
            if not direct_chunks:
                return {
                    "answer": GENERATION_FAILED_MESSAGE,
                    "sources": [],
                    "suggested_questions": [],
                    "not_found": False,
                    "generation_failed": True,
                    "safety_level": "normal",
                }, None
            chunks = []

        if direct_chunks:
            # The referenced item leads the passage list; drop any semantic
            # duplicates of it so the prompt never repeats the same text.
            direct_keys = {
                (c["metadata"]["book"], c["metadata"]["item_number"])
                for c in direct_chunks
            }
            chunks = direct_chunks + [
                c
                for c in chunks
                if (c["metadata"]["book"], c["metadata"]["item_number"])
                not in direct_keys
            ]

        fallback_note: str | None = None
        if not chunks and book_filter:
            try:
                fallback_chunks = retrieve(search_query)
            except Exception:
                logger.exception("book-filter fallback retrieve failed")
                fallback_chunks = []
            if fallback_chunks:
                chunks = fallback_chunks
                fallback_note = BOOK_FALLBACK_NOTE.format(book=book_filter)
                logger.info(
                    "book_filter %s empty; fell back to full-collection search",
                    book_filter,
                )

        chunks = append_chapter_commentary(chunks)

        try:
            level = sensitivity_future.result(timeout=_SENSITIVITY_TIMEOUT_S)
        except Exception:
            logger.exception("classify_sensitivity slow/failed; defaulting to normal")
            level = "normal"
    finally:
        executor.shutdown(wait=False)

    if level == "crise":
        return _crisis_exit(), None

    if level == "abalo":
        chunks = filter_sensitive_chunks(chunks)

    if not chunks:
        logger.warning("no chunks retrieved for /chat; returning not_found")
        return {
            "answer": (
                NOT_FOUND_MESSAGE + "\n\n" + CRISIS_NOTE
                if topic_note
                else NOT_FOUND_MESSAGE
            ),
            "sources": [],
            "suggested_questions": [],
            "not_found": True,
            "generation_failed": False,
            "safety_level": level,
        }, None

    sensitive = level == "abalo"
    add_caveat = needs_medical_caveat(question) or sensitive
    system, messages = build_messages(
        question,
        chunks,
        history,
        settings.max_history_turns,
        add_caveat=add_caveat,
        sensitive=sensitive,
        profile=profile,
    )
    return None, {
        "system": system,
        "messages": messages,
        "profile": profile,
        "chunks": chunks,
        "level": level,
        "sensitive": sensitive,
        "topic_note": topic_note,
        "fallback_note": fallback_note,
    }


def _postprocess(
    answer: str, ctx: dict
) -> tuple[str, list[dict], list[str], list[dict]]:
    """Turns the model's raw text into what gets displayed and cited. Shared by
    both lanes, and the reason a streamed `done` payload is identical to what
    POST /chat returns. May raise — the caller treats that as a failed
    generation."""
    chunks = ctx["chunks"]

    # Log-only monitors. These run on both lanes because they mutate
    # nothing — they only record what the model did. Wrapped so a monitor
    # can never fail an otherwise-good request. Citations are extracted
    # BEFORE any stripping below.
    try:
        report = validate_model_citations(
            extract_model_citations(answer), retrieved_ids(chunks)
        )
        if not report["confiavel"]:
            logger.warning(
                "model cited ids outside the retrieved set: %s",
                report["alucinadas"],
            )
        personifications = counts_personification(answer)
        if personifications:
            logger.warning("personification of 'o Espiritismo': %d", personifications)
    except Exception:
        logger.exception("log-only citation/personification monitor failed")

    # Everything that MUTATES the answer or its sources is gated on the
    # prose lane, so Tasks 1-6 leave the current provider's output identical.
    prose_lane = settings.prose_provider is not None
    debris_suggestions: list[str] = []
    if prose_lane:
        answer = strip_model_citations(answer)
        if not answer.strip():
            # The model's entire reply was a citation; there is nothing
            # left to show. Treat it as a generation failure rather than
            # returning an empty bubble.
            raise ValueError("answer emptied by strip_model_citations")
        # riv-ai-v2 scatters marker lines mid-text (emoji-prefixed, not
        # anchored to the end), which strip_trailing_markers below cannot
        # see. Clear that debris first so the end-anchored pass only has
        # to catch a well-formed trailer, if any remains.
        answer, debris_suggestions = strip_marker_debris(answer)
    answer, marker_chunks, suggested_questions = strip_trailing_markers(answer, chunks)
    if prose_lane and not suggested_questions:
        suggested_questions = debris_suggestions
    if prose_lane:
        # riv-ai-v2 does not honor [FONTES:] — it emits question numbers or
        # invents references. Attribution is computed from the vector store
        # instead, so the model never decides its own citations.
        try:
            chunks = attribute_sources(answer, chunks)
        except Exception:
            logger.exception("attribute_sources failed; falling back to marker chunks")
            chunks = marker_chunks
        # Backstop for the prompt rule: follow-ups live in [SEGUIR] only.
        answer = strip_trailing_question(answer)
    else:
        # Current provider: it honors [FONTES:], so keep today's behavior.
        chunks = marker_chunks
    # System vocabulary the reader cannot make sense of — they do not know a
    # retrieval step exists. The prompt forbids these by name and the model used
    # one anyway (2026-07-28), so the rule gets a backstop. Logged rather than
    # silently fixed: the substitution hides the symptom, and the count is the
    # only way to tell whether the prompt rule is working at all.
    answer, internal_terms = strip_internal_terms(answer)
    if internal_terms:
        logger.warning("internal vocabulary rewritten: %d", internal_terms)

    if ctx["fallback_note"]:
        answer = ctx["fallback_note"] + answer

    # Resolved against what was actually retrieved; an index outside that list
    # is dropped here rather than shown. Last, so positions index into the text
    # the reader really sees — including the fallback note prepended above.
    # Under `full` the marker becomes the reference itself, written from
    # metadata. The model was asked to write references and measurably does not
    # (2026-07-28 A/B); it does reliably mark WHERE they go, which is the part
    # only it can do. The canonical form is the part only code can guarantee.
    answer, inline_refs = extract_passage_refs(answer, ctx["chunks"])

    # A quotation attributed to the works that is in none of the retrieved
    # passages is fabricated doctrine, which this project treats as
    # unacceptable — so the answer does not get shown, on any lane.
    #
    # Deliberately NOT behind the prose-lane gate above. That gate exists to
    # keep the current provider's output identical, and it is exactly why this
    # failure reached production untouched on 2026-07-28: everything that could
    # have caught it was switched off for the lane actually running.
    #
    # Runs LAST, on the finished text. Running it first cost a correct answer in
    # the 2026-07-28 probe: the model had written "[fonte 3]" inside a
    # quotation, and comparing a marker against the corpus can only ever fail.
    # The check belongs on what the reader will actually see.
    #
    # The whole answer goes, not just the sentence: the same improvisation that
    # invented a quotation wrote the paragraphs around it. In the case this was
    # built from, three paragraphs about "duplo etéreo" preceded the fake quote
    # and none of them came from the works either.
    unsupported = find_unsupported_quotes(answer, ctx["chunks"])
    if unsupported:
        logger.warning("fabricated quotation, answer withheld: %s", unsupported[:3])
        raise UnsupportedQuoteError(unsupported)

    # Only now, with the guard satisfied on what the MODEL wrote, does code
    # write the references in. Doing it earlier fed the guard its own output.
    if ctx["profile"].citation_precision == "full":
        answer, inline_refs = render_references(answer, inline_refs)

    return answer, chunks, suggested_questions, inline_refs


def _finalize(answer: str | None, ctx: dict, generation_failed: bool) -> dict:
    """Assembles the response body from the model's text. The single place both
    POST /chat and the stream's `done` event go through, so the two can never
    drift apart."""
    chunks: list[dict] = []
    suggested_questions: list[str] = []
    inline_refs: list[dict] = []
    not_found_override = False
    if generation_failed:
        answer = GENERATION_FAILED_MESSAGE
    else:
        try:
            answer, chunks, suggested_questions, inline_refs = _postprocess(answer, ctx)
        except UnsupportedQuoteError:
            # Not a generation failure — the model answered, and what it said
            # cannot be shown. "I did not find this in the works" is both the
            # honest thing and, for a question like "duplo etéreo", the true one.
            answer = NOT_FOUND_MESSAGE
            chunks, suggested_questions, inline_refs = [], [], []
            not_found_override = True
        except Exception:
            logger.exception("chat answer post-processing failed")
            answer = GENERATION_FAILED_MESSAGE
            chunks, suggested_questions, inline_refs = [], [], []
            generation_failed = True

    if ctx["sensitive"]:
        # A distressed turn is not steered toward "explore more" chips.
        suggested_questions = []

    if ctx["topic_note"]:
        # Deterministic: any suicide-topic question carries the CVV note.
        answer = answer + "\n\n" + CRISIS_NOTE

    seen: set[tuple] = set()
    sources = []
    for chunk in chunks:
        m = chunk["metadata"]
        key = (m["book"], m.get("chapter_title", ""), m.get("item_number", ""))
        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "book": m["book"],
                    "chapter": m.get("chapter_title") or None,
                    "chapter_ref": m.get("chapter") or None,
                    "item_number": (
                        m["item_number"]
                        if has_real_item_number(m.get("item_number"))
                        else None
                    ),
                    "excerpt": chunk["content"],
                }
            )

    return {
        "answer": answer,
        # Dropped along with the sources on a failed generation: a reference
        # into text that was replaced by an error message points nowhere.
        "inline_refs": [] if generation_failed else inline_refs,
        "sources": [] if generation_failed else sources,
        "suggested_questions": suggested_questions,
        "not_found": not_found_override,
        "generation_failed": generation_failed,
        "safety_level": ctx["level"],
    }


def generate(
    question: str,
    history: list[dict],
    book_filter: str | None = None,
    anchor_text: str | None = None,
    profile: ResponseProfile = CHAT_DEFAULT,
) -> dict:
    early, ctx = _prepare(question, history, book_filter, anchor_text, profile)
    if early is not None:
        return early

    try:
        answer = prose_completion(ctx["system"], ctx["messages"])
        generation_failed = False
    except Exception:
        logger.exception("chat generation LLM call failed")
        answer, generation_failed = None, True

    return _finalize(answer, ctx, generation_failed)


def generate_stream(
    question: str,
    history: list[dict],
    book_filter: str | None = None,
    anchor_text: str | None = None,
    profile: ResponseProfile = CHAT_DEFAULT,
) -> Iterator[tuple[str, object]]:
    """The same answer as generate(), yielded as ("token", text) pairs followed
    by exactly one ("done", result).

    Every short-circuit — small talk, the crisis exit, a retrieval failure, no
    chunks — yields its `done` and nothing else: those responses are decided in
    code and arrive whole, never letter by letter.

    Tokens pass through StreamBuffer, so a trailer marker can never reach the
    screen. The `done` payload is built by _finalize from the complete text, and
    is the source of truth: a client that replaces its accumulated text with it
    ends up byte-identical to POST /chat.
    """
    early, ctx = _prepare(question, history, book_filter, anchor_text, profile)
    if early is not None:
        yield "done", early
        return

    buffer = StreamBuffer()
    # The trailer buffer cannot do this job: it seals on the first opening,
    # because a trailer is terminal by contract, and inline markers sit in the
    # middle of prose. Composed after it so the trailer is handled first.
    markers = InlineMarkerFilter("fonte")
    # Quoted text is held until it can be checked. Without this the guard in
    # _postprocess only fires after every token has been displayed, so a
    # fabricated quotation is read and then retracted — which is the one thing
    # the guard exists to prevent (found in production 2026-07-28).
    quotes = StreamingQuoteGuard(ctx["chunks"])
    pieces: list[str] = []
    generation_failed = False
    try:
        for piece in prose_completion_stream(ctx["system"], ctx["messages"]):
            pieces.append(piece)
            safe = quotes.feed(markers.feed(buffer.feed(piece)))
            if quotes.violated:
                # Stop reading the model out loud. _postprocess reaches the same
                # verdict on the complete text and builds the not-found answer,
                # so the two lanes still agree.
                logger.warning(
                    "fabricated quotation mid-stream, answer abandoned: %s",
                    quotes.offending,
                )
                break
            if safe:
                yield "token", safe
        if not quotes.violated:
            tail = quotes.feed(markers.flush()) + quotes.flush()
            if tail:
                yield "token", tail
    except Exception:
        # Mid-stream failure: whatever is on screen gets replaced by the
        # `done` payload below, so the reader is never left with half an answer.
        logger.exception("chat streaming LLM call failed")
        generation_failed = True

    yield "done", _finalize("".join(pieces), ctx, generation_failed)
