import concurrent.futures
import logging
from typing import Iterator

from src.core.config import settings
from src.rag.curador import curar
from src.rag.explicador_prompt import (
    build_explicador_messages,
    parse_explicador_json,
)
from src.rag.inline_refs import InlineMarkerFilter, extract_item_refs
from src.rag.json_stream import JsonFieldStreamer
from src.rag.llm_client import get_client
from src.rag.profile import STUDY_DEFAULT, ResponseProfile
from src.rag.prose import delta_text
from src.rag.quote_check import find_unsupported_quotes
from src.rag.retriever import (
    chapter_commentary,
    filter_sensitive_chunks,
    filter_uncitable_chunks,
    retrieve,
    retrieve_by_item,
    retrieved_summary,
)

logger = logging.getLogger(__name__)


def prepare_study(
    book: str,
    item_number: str,
    chapter: str | None = None,
    profile: ResponseProfile = STUDY_DEFAULT,
) -> dict | None:
    """Everything before the model call: retrieval, related items, chapter
    commentary, prompt build. Returns None when the item does not exist.

    Split out so the streaming and non-streaming lanes run the same preparation
    and cannot drift apart — the arrangement the chat lane already uses. It is
    also what lets the route answer 404 before opening a stream: a real
    not-found stays an HTTP 404 instead of becoming an SSE event.
    """
    # Note: retrieve_by_item failures are left unhandled here (surface as a
    # 500), rather than mapped to the 404 "item not found" response — a DB
    # failure and a real not-found are different situations and shouldn't
    # look the same to the client.
    chunks = retrieve_by_item(book, item_number, chapter)
    if not chunks:
        return None

    original_text = "\n\n".join(c["content"] for c in chunks)
    footnote_context = "\n\n".join(
        c["footnote_context"] for c in chunks if c.get("footnote_context")
    )

    related_query = chunks[0]["content"]
    try:
        all_related = retrieve(related_query, top_k=6)
    except Exception:
        logger.exception("related-items retrieve failed in explicador")
        all_related = []
    # The darkest O Céu e o Inferno testimony is filtered out of the RELATED
    # items unconditionally, without waiting for a sensitivity tier.
    #
    # The studied item is not filtered: opening it is a deliberate act, and
    # someone who navigates to that chapter has chosen it. A related item is the
    # opposite — the system offering something nobody asked for. Suggesting a
    # suicide testimony beside a passage about suffering is a choice this code
    # makes, and the daily passage opens through here every morning.
    related = [
        r
        for r in filter_uncitable_chunks(filter_sensitive_chunks(all_related))
        if not (
            r["metadata"]["item_number"] == item_number
            and r["metadata"]["book"] == book
        )
    ][:3]

    commentary = chapter_commentary(book, chapter or "", item_number)

    # Explicador is PINNED to the JSON lane, exactly like Reflexivo, and
    # deliberately reads no setting: `PROSE_PROVIDER` is one switch, so honouring
    # it here would drag /study along whenever the prose lane is enabled for
    # /chat. The two modes have opposite evidence and must be able to sit on
    # different models.
    #
    # Why /study stays on the large model (measured 2026-07-25, temperature=0 on
    # the prose lane, so attributable): riv-ai-v2 failed the marker output
    # contract on 3 of 3 study items, and still 2 of 3 after a contradiction in
    # the marker prompt was fixed. It also misattributed a passage's own work
    # ("O Evangelho Segundo o Espiritismo" for O Livro dos Espíritos 886). /chat
    # tolerates a lighter voice because it is conversation; /study is where a
    # reader goes to CHECK what a work says, and a wrong attribution there
    # contaminates the study itself.
    #
    # The marker template and `parse_explicador_markers` are kept, reachable
    # from `scripts/compare_generators.py`, so a future model can be re-evaluated
    # without rebuilding this. They are not on the request path.
    system, messages = build_explicador_messages(
        original_text,
        related,
        footnote_context=footnote_context,
        chapter_commentary_chunks=commentary,
        markers=False,
        profile=profile,
    )

    return {
        "chunks": chunks,
        "original_text": original_text,
        "related": related,
        "commentary": commentary,
        "system": system,
        "messages": messages,
    }


def build_chapter_context(ctx: dict) -> list[dict]:
    """The chapter siblings that went into the prompt, as references a reader
    can open — one entry per item, subchunks rejoined in order.

    Neutral by construction: these are the chapter's other items as retrieved,
    verses and Kardec's commentary alike, with no claim about which is which.
    Nothing in the metadata separates them, and guessing would risk presenting
    a gospel verse as Kardec's own words.

    Section placeholders ('section-N', the parser's marker for unnumbered
    chapter headings) are dropped: they are not items anyone can look up.
    """
    grouped: dict[str, dict] = {}
    for chunk in ctx.get("commentary") or []:
        meta = chunk["metadata"]
        item = meta.get("item_number") or ""
        if not item.isdigit():
            continue
        entry = grouped.setdefault(
            item,
            {
                "book": meta["book"],
                "chapter_title": meta.get("chapter_title") or None,
                # The machine chapter id, so a reference can name the chapter.
                # Item numbers restart every chapter in Evangelho and Céu e
                # Inferno; without this the modal shows a number that could be
                # any of a dozen chapters.
                "chapter_ref": meta.get("chapter") or None,
                "item_number": item,
                "parts": [],
            },
        )
        entry["parts"].append(chunk["content"])

    return [
        {
            "book": e["book"],
            "chapter_title": e["chapter_title"],
            "chapter_ref": e["chapter_ref"],
            "item_number": e["item_number"],
            "excerpt": " ".join(e["parts"]),
        }
        for e in grouped.values()
    ]


def _parse(raw: str | None) -> tuple[str, list[str], list[str]]:
    contexto, conceitos, perguntas = parse_explicador_json(raw)
    if not contexto.strip():
        # parse_explicador_json never raises: its last resort is a regex
        # sweep that yields ("", [], []). Without this check an unreadable
        # response reaches the client as an EMPTY contexto with
        # generation_failed=False — a blank panel instead of an error. The
        # marker path used to raise here; the JSON path has to be told.
        raise ValueError("explicador returned no contexto")
    return contexto, conceitos, perguntas


def build_sources(ctx: dict) -> list[dict]:
    """The passage's own references. Known from retrieval alone, so the stream
    can show the text being studied before the explanation of it starts."""
    return [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in ctx["chunks"]
    ]


def _finalize(
    ctx: dict,
    contexto: str,
    conceitos_chave: list[str],
    perguntas: list[str],
    related_items: list,
    generation_failed: bool,
) -> dict:
    """The single place the response body is assembled, so POST /study and the
    stream's `done` event cannot describe the same item differently."""
    sources = build_sources(ctx)

    # Inline markers are resolved against what was actually retrieved; anything
    # naming an item outside it is dropped here rather than shown. The clean
    # text is what the reader sees, in both lanes.
    chapter_context = build_chapter_context(ctx)
    contexto, inline_refs = extract_item_refs(contexto, chapter_context)

    # A quotation attributed to the works that is in none of the retrieved text
    # is fabricated doctrine — and /study is where a reader goes to CHECK what a
    # work says, so a wrong attribution here contaminates the study itself. The
    # guard ran only on /chat until now; the reasoning applies harder here.
    #
    # Checked after the markers are stripped, on the text the reader will see:
    # running it on marked-up text compares code's own output against the corpus
    # and withholds correct answers, which is how this went wrong on /chat.
    available = ctx["chunks"] + (ctx.get("commentary") or []) + ctx.get("related", [])
    unsupported = find_unsupported_quotes(contexto, available)
    if unsupported:
        logger.warning("fabricated quotation in /study, withheld: %s", unsupported[:2])
        contexto, conceitos_chave, perguntas, inline_refs = "", [], [], []
        generation_failed = True

    return {
        "original_text": ctx["original_text"],
        "contexto": contexto,
        "inline_refs": inline_refs,
        "conceitos_chave": conceitos_chave,
        "perguntas": perguntas,
        "related_items": related_items,
        "sources": sources,
        "chapter_context": chapter_context,
        "generation_failed": generation_failed,
        # Log-only; `StudyResponse` is built from named fields, so this never
        # reaches the client. `available` and not `ctx["chunks"]` because all
        # three sets go to the prompt — and it was exactly that mixture that
        # produced, on 2026-07-28, a citation to an item from another chapter
        # presented as belonging to this one.
        "retrieved": retrieved_summary(available),
    }


def explicar(
    book: str,
    item_number: str,
    chapter: str | None = None,
    profile: ResponseProfile = STUDY_DEFAULT,
) -> dict | None:
    ctx = prepare_study(book, item_number, chapter, profile)
    if ctx is None:
        return None

    def _call_explicador():
        response = get_client("json").chat.completions.create(
            model=settings.resolved_chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": ctx["system"]}] + ctx["messages"],
        )
        return _parse(response.choices[0].message.content)

    contexto = ""
    conceitos_chave: list[str] = []
    perguntas: list[str] = []
    generation_failed = False

    # curar() makes its own independent provider call and only needs `related`,
    # which is already available — run both LLM calls concurrently instead
    # of paying their latency twice in sequence.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        explicador_future = executor.submit(_call_explicador)
        curador_future = executor.submit(curar, ctx["original_text"], ctx["related"])

        try:
            contexto, conceitos_chave, perguntas = explicador_future.result()
        except Exception:
            logger.exception("explicador LLM call/parse failed")
            generation_failed = True

        related_items = curador_future.result()

    return _finalize(
        ctx, contexto, conceitos_chave, perguntas, related_items, generation_failed
    )


def explicar_stream(ctx: dict) -> Iterator[tuple[str, object]]:
    """Yields ("token", text) as the explanation is written, then ("done", body).

    `done` is the source of truth: the accumulated JSON is parsed at the end
    with the same `_parse` the non-streaming lane uses, so a streamed /study
    ends up identical to POST /study. The tokens are a preview of one field —
    `contexto` — and everything else in the body arrives whole with `done`.

    Take `ctx` from prepare_study(); a missing item is answered before any of
    this runs.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        curador_future = executor.submit(curar, ctx["original_text"], ctx["related"])

        raw = ""
        contexto, conceitos_chave, perguntas = "", [], []
        generation_failed = False
        streamer = JsonFieldStreamer("contexto")
        # The streamed contexto carries the inline markers; they must never
        # flash on screen, and the text a reader watches arrive has to end up
        # identical to the clean text `done` carries.
        markers = InlineMarkerFilter("item")

        try:
            stream = get_client("json").chat.completions.create(
                model=settings.resolved_chat_model,
                max_tokens=1024,
                messages=[{"role": "system", "content": ctx["system"]}]
                + ctx["messages"],
                stream=True,
            )
            for chunk in stream:
                text = delta_text(chunk)
                if not text:
                    continue
                raw += text
                piece = markers.feed(streamer.feed(text))
                if piece:
                    yield "token", piece
            tail = markers.flush()
            if tail:
                yield "token", tail
            contexto, conceitos_chave, perguntas = _parse(raw)
        except Exception:
            # Same outcome as the non-streaming lane: an unusable response is
            # generation_failed, not a 500. Whatever reached the screen is
            # replaced by `done`, so a half-written explanation never stands as
            # the answer.
            logger.exception("explicador streaming LLM call/parse failed")
            generation_failed = True
            contexto, conceitos_chave, perguntas = "", [], []

        related_items = curador_future.result()
    finally:
        executor.shutdown(wait=False)

    yield "done", _finalize(
        ctx, contexto, conceitos_chave, perguntas, related_items, generation_failed
    )
