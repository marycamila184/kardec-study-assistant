import concurrent.futures
import logging

from src.core.config import settings
from src.rag.curador import curar
from src.rag.explicador_prompt import (
    build_explicador_messages,
    parse_explicador_json,
)
from src.rag.llm_client import get_client
from src.rag.retriever import chapter_commentary, retrieve, retrieve_by_item

logger = logging.getLogger(__name__)


def explicar(book: str, item_number: str, chapter: str | None = None) -> dict | None:
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
    related = [
        r
        for r in all_related
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
    )

    def _call_explicador():
        response = get_client("json").chat.completions.create(
            model=settings.resolved_chat_model,
            max_tokens=1024,
            messages=[{"role": "system", "content": system}] + messages,
        )
        contexto, conceitos, perguntas = parse_explicador_json(
            response.choices[0].message.content
        )
        if not contexto.strip():
            # parse_explicador_json never raises: its last resort is a regex
            # sweep that yields ("", [], []). Without this check an unreadable
            # response reaches the client as an EMPTY contexto with
            # generation_failed=False — a blank panel instead of an error. The
            # marker path used to raise here; the JSON path has to be told.
            raise ValueError("explicador returned no contexto")
        return contexto, conceitos, perguntas

    contexto = ""
    conceitos_chave: list[str] = []
    perguntas: list[str] = []
    generation_failed = False

    # curar() makes its own independent provider call and only needs `related`,
    # which is already available — run both LLM calls concurrently instead
    # of paying their latency twice in sequence.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        explicador_future = executor.submit(_call_explicador)
        curador_future = executor.submit(curar, original_text, related)

        try:
            contexto, conceitos_chave, perguntas = explicador_future.result()
        except Exception:
            logger.exception("explicador LLM call/parse failed")
            generation_failed = True

        related_items = curador_future.result()

    sources = [
        {
            "book": c["metadata"]["book"],
            "chapter_title": c["metadata"].get("chapter_title") or None,
            "item_number": c["metadata"]["item_number"],
        }
        for c in chunks
    ]

    return {
        "original_text": original_text,
        "contexto": contexto,
        "conceitos_chave": conceitos_chave,
        "perguntas": perguntas,
        "related_items": related_items,
        "sources": sources,
        "generation_failed": generation_failed,
    }
