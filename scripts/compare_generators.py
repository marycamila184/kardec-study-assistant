"""Side-by-side comparison of the prose lane against the current provider.

Run each question through both lanes and report, per lane, the two numbers that
decide whether the swap is an improvement:

  - mean groundedness: how close answers stay to their retrieved passages
  - hallucinated-citation rate: how often the model cites outside that set

Also runs each `/study` item (STUDY_ITEMS) through Explicador on both lanes —
the branch's riskiest change is the marker-protocol output contract on an 8B
model, and `study_failure_rate` is the number that tells you whether it holds.

Also prints the per-chunk answer-to-chunk cosine distribution across every
/chat question on each lane — the data needed to calibrate
`settings.source_min_similarity` (see the comment there).

Read as a *comparison* between lanes, never as absolute thresholds.

Each lane is run and persisted independently (`logs/lane-<name>.json`), written
after every single question rather than at the end. The 2026-07-25 run lost all
fifteen baseline answers to a mid-run provider quota error, because both lanes
ran in one process and nothing was written until the last one finished. Now a
lane that dies keeps everything it already produced, and the lanes can be run
hours apart — the prose lane costs nothing locally, the baseline waits for
quota. The report is built from whatever lane files exist.

Usage:
    uv run python -m scripts.compare_generators --lane prose   # local, free
    uv run python -m scripts.compare_generators --lane json    # needs quota
    uv run python -m scripts.compare_generators --report-only > logs/ab.md
"""

import argparse
import json
import os
import re
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

QUESTIONS = [
    "o que é o espírito?",
    "o que acontece depois da morte?",
    "o que é a lei de causa e efeito?",
    "por que existe o sofrimento?",
    "o que Kardec diz sobre a caridade?",
    "o que é a reencarnação e por que ela existe?",
    "qual a diferença entre alma e espírito?",
    "o que são os espíritos protetores?",
    "o que é a prece segundo a doutrina?",
    "o que é o perispírito?",
    "como funciona a mediunidade?",
    "o que é o livre-arbítrio?",
    "o que a doutrina diz sobre o perdão?",
    "o que são as provações?",
    "qual o papel da família na doutrina?",
]

STUDY_ITEMS = [
    ("O Livro dos Espíritos", "625"),
    ("O Livro dos Espíritos", "886"),
    ("O Livro dos Médiuns", "132"),
]


# An inline reference the reader sees in the prose — "item 659", "questão 872",
# a work's name in quotes. Distinct from the [FONTES:] trailer, which is machine
# -readable and stripped before display.
_INLINE_REF = re.compile(r"item\s+\d+|quest[ãa]o\s+\d+|\"O\s+[A-ZÀ-Ý]", re.IGNORECASE)


def style_metrics(rows: list[dict]) -> dict:
    """Length and inline-reference density.

    Unlike every judgment-based metric in these harnesses, these are
    deterministic properties of the text: they do not depend on a model's
    opinion and do not move between runs. That makes them the only numbers here
    that can settle a small prompt change on their own.
    """
    if not rows:
        return {"mean_chars": 0.0, "mean_inline_refs": 0.0, "mean_paragraphs": 0.0}
    n = len(rows)
    return {
        "mean_chars": sum(len(r["answer"]) for r in rows) / n,
        "mean_inline_refs": sum(len(_INLINE_REF.findall(r["answer"])) for r in rows) / n,
        "mean_paragraphs": sum(r["answer"].count("\n\n") + 1 for r in rows) / n,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"mean_groundedness": 0.0, "hallucinated_citation_rate": 0.0}
    n = len(rows)
    return {
        "mean_groundedness": sum(r["groundedness"] for r in rows) / n,
        "hallucinated_citation_rate": sum(1 for r in rows if not r["confiavel"]) / n,
    }


def summarize_study(rows: list[dict]) -> dict:
    """Two /study numbers, kept separate for a reason worth remembering.

    - `study_failure_rate` — what the USER sees.
    - `marker_failure_rate` — whether the prose model honored the output
      contract at all.

    They used to diverge badly: while Explicador still fell back to the JSON
    lane on a format failure, `study_failure_rate` read 0.0 on a run where the
    prose model had honored the contract 0 of 3 times — every "prose lane"
    contexto in that report was written by the 70B fallback. Reading only the
    first number gave a conclusion that was exactly backwards.

    /study is now pinned to the JSON lane and the fallback is gone, so on the
    harness's reconstructed prose lane the two coincide. They stay separate
    because that coincidence is a property of today's design, not a guarantee.
    """
    if not rows:
        return {
            "study_failure_rate": 0.0,
            "marker_failure_rate": 0.0,
            "misattribution_rate": 0.0,
            "unsupplied_book_rate": 0.0,
        }
    n = len(rows)
    return {
        "study_failure_rate": sum(1 for r in rows if r["generation_failed"]) / n,
        "marker_failure_rate": sum(1 for r in rows if r.get("marker_failed")) / n,
        # Naming the wrong work for the passage under study — a different error
        # from writing a wrong citation, and invisible to the citation checks.
        "misattribution_rate": sum(1 for r in rows if r.get("misattributions")) / n,
        "unsupplied_book_rate": sum(1 for r in rows if r.get("unsupplied_books")) / n,
    }


class _ProseClientProxy:
    """Makes `explicar`'s json-lane call go to the prose provider instead.

    `explicar` hardcodes `get_client("json")` and `settings.resolved_chat_model`
    since the pin, so both have to be substituted at the call. Mirrors the prose
    lane's own shape: prose model, temperature=0.
    """

    def __init__(self, client, model):
        self._client, self._model = client, model

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, model=None, **kwargs):
        return self._client.chat.completions.create(
            model=self._model, temperature=0, **kwargs
        )


@contextmanager
def _explicador_on_the_prose_lane():
    """Reconstructs the prose-lane /study call the production path no longer has.

    Explicador is pinned to the JSON lane in `src/` — /study must not follow
    `PROSE_PROVIDER`. Measuring the prose lane therefore has to be done from
    outside, the same way `compare_reflect.py` measures Reflexivo, so the
    evaluation never becomes a reason to loosen the pin.

    Yields an object whose `.count` is the number of marker-parse failures.
    Since the pin removed the JSON fallback, a marker failure now IS a
    generation failure — but it is still counted separately here, because on
    this lane the two coincide only by accident of the current design.
    """
    from src.core.config import settings
    from src.rag import explicador as exp
    from src.rag.explicador_prompt import (
        build_explicador_messages,
        parse_explicador_markers,
    )
    from src.rag.llm_client import get_client

    class _Counter:
        count = 0

    counter = _Counter()

    def marker_build(*args, **kwargs):
        kwargs["markers"] = True
        return build_explicador_messages(*args, **kwargs)

    def counting_parse(text):
        try:
            return parse_explicador_markers(text)
        except ValueError:
            counter.count += 1
            raise

    proxy = _ProseClientProxy(get_client("prose"), settings.resolved_prose_model)
    with ExitStack() as stack:
        stack.enter_context(patch.object(exp, "build_explicador_messages", marker_build))
        stack.enter_context(patch.object(exp, "parse_explicador_json", counting_parse))
        stack.enter_context(patch.object(exp, "get_client", lambda role="json": proxy))
        yield counter


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = pct * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def similarity_distribution(all_sims: list[float]) -> dict:
    """Distribution of per-chunk answer-to-chunk cosines across every /chat
    question on a lane — the data `source_min_similarity` should be picked
    from, per the comment in src/core/config.py."""
    if not all_sims:
        return {
            "min": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "max": 0.0,
            "kept_at_0.3": 0,
            "kept_at_0.4": 0,
            "kept_at_0.5": 0,
            "kept_at_0.6": 0,
        }
    s = sorted(all_sims)
    return {
        "min": s[0],
        "median": _percentile(s, 0.5),
        "p25": _percentile(s, 0.25),
        "p75": _percentile(s, 0.75),
        "max": s[-1],
        "kept_at_0.3": sum(1 for v in all_sims if v >= 0.3),
        "kept_at_0.4": sum(1 for v in all_sims if v >= 0.4),
        "kept_at_0.5": sum(1 for v in all_sims if v >= 0.5),
        "kept_at_0.6": sum(1 for v in all_sims if v >= 0.6),
    }


def format_report(pairs: list[dict]) -> str:
    lines = ["# RIV AI v2 vs current provider", "", "## /chat", ""]
    for p in pairs:
        lines += [
            f"## {p['question']}",
            "",
            "### prose lane (riv-ai-v2)",
            "",
            p["prose"]["answer"],
            "",
            f"_groundedness {p['prose']['groundedness']:.3f} · "
            f"citations trustworthy: {p['prose']['confiavel']}_",
            "",
            "### json lane (current)",
            "",
            p["json"]["answer"],
            "",
            f"_groundedness {p['json']['groundedness']:.3f} · "
            f"citations trustworthy: {p['json']['confiavel']}_",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def format_study_report(pairs: list[dict]) -> str:
    """/study section of the report (Finding 1) — per-item contexto,
    conceitos_chave, and generation_failed on both lanes."""
    lines = ["## /study (Explicador)", ""]
    for p in pairs:
        lines += [
            f"### {p['book']} — item {p['item_number']}",
            "",
            "**prose lane (riv-ai-v2)**"
            + (
                "  ⚠️ **marker parse failed — text below is the 70B fallback, "
                "not riv-ai**"
                if p["prose"].get("marker_failed")
                else ""
            ),
            "",
            f"- contexto: {p['prose']['contexto']}",
            f"- conceitos_chave: {p['prose']['conceitos_chave']}",
            f"- generation_failed: {p['prose']['generation_failed']}",
            f"- marker_failed: {p['prose'].get('marker_failed')}",
            f"- groundedness: {p['prose']['groundedness']:.3f}",
            "",
            "**json lane (current)**",
            "",
            f"- contexto: {p['json']['contexto']}",
            f"- conceitos_chave: {p['json']['conceitos_chave']}",
            f"- generation_failed: {p['json']['generation_failed']}",
            f"- groundedness: {p['json']['groundedness']:.3f}",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


LANE_DIR = "logs"


def lane_path(lane: str) -> str:
    return os.path.join(LANE_DIR, f"lane-{lane}.json")


def save_lane(lane: str, chat: list[dict], study: list[dict], sims: list[float]) -> None:
    """Persist a lane's results so far.

    Called after every question, not once at the end — a provider quota error
    mid-run must cost the remaining questions, never the finished ones. Written
    to a temp file and renamed so a crash mid-write cannot leave a truncated
    file that later reads as valid-but-short.
    """
    os.makedirs(LANE_DIR, exist_ok=True)
    payload = {"lane": lane, "chat": chat, "study": study, "similarities": sims}
    tmp = lane_path(lane) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, lane_path(lane))


def load_lane(lane: str) -> dict | None:
    """Reads a persisted lane, or None when it has not been run yet."""
    try:
        with open(lane_path(lane), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def _run_lane(
    prose_provider: str | None, lane: str = "prose"
) -> tuple[list[dict], list[dict], list[float]]:
    """Runs every question and every /study item with the prose lane pointed
    at `prose_provider`.

    `settings` is a module-level singleton built at import time, so setting an
    env var here would be read too late. Mutate the setting directly and clear
    the client cache so the next call rebuilds against the new provider.

    Returns (chat_rows, study_rows, per_chunk_similarities) — the third is the
    flattened list of every /chat answer-to-chunk cosine on this lane, used to
    calibrate `source_min_similarity` (Finding 3).
    """
    from src.core.config import settings
    from src.rag import llm_client
    from src.rag.citations import (
        extract_model_citations,
        misattributions,
        retrieved_ids,
        unsupplied_books,
        validate_model_citations,
    )
    from src.rag.explicador import explicar
    from src.rag.generator import generate
    from src.rag.groundedness import groundedness_score, per_chunk_similarities
    from src.rag.retriever import retrieve, retrieve_by_item

    settings.prose_provider = prose_provider
    llm_client._clients.clear()

    rows = []
    all_sims: list[float] = []
    for q in QUESTIONS:
        result = generate(q, [])
        chunks = retrieve(q)
        report = validate_model_citations(
            extract_model_citations(result["answer"]), retrieved_ids(chunks)
        )
        rows.append(
            {
                "question": q,
                "answer": result["answer"],
                "groundedness": groundedness_score(result["answer"], chunks),
                "confiavel": report["confiavel"],
            }
        )
        all_sims.extend(per_chunk_similarities(result["answer"], chunks))
        save_lane(lane, rows, [], all_sims)

    study_rows = []
    for book, item_number in STUDY_ITEMS:
        if prose_provider is not None:
            with _explicador_on_the_prose_lane() as marker_watch:
                result = explicar(book, item_number)
        else:
            marker_watch = type("N", (), {"count": 0})()
            result = explicar(book, item_number)
        item_chunks = retrieve_by_item(book, item_number)
        contexto = result["contexto"] if result else ""
        # Works the model could legitimately name: the item's own, plus every
        # work among the related passages Explicador showed it. Mirrors the
        # related-items query in explicar() so the allowed set matches what the
        # model actually saw.
        supplied = [book] + [
            c["metadata"]["book"]
            for c in (retrieve(item_chunks[0]["content"], top_k=6) if item_chunks else [])
        ]
        study_rows.append(
            {
                "book": book,
                "item_number": item_number,
                "contexto": contexto,
                "conceitos_chave": result["conceitos_chave"] if result else [],
                "generation_failed": result["generation_failed"] if result else True,
                # True => this contexto came from the 70B fallback, NOT from the
                # prose model, even though the row sits in the prose lane.
                "marker_failed": marker_watch.count > 0,
                "unsupplied_books": sorted(unsupplied_books(contexto, supplied)),
                "misattributions": misattributions(contexto, book),
                "groundedness": groundedness_score(contexto, item_chunks),
            }
        )
        save_lane(lane, rows, study_rows, all_sims)

    return rows, study_rows, all_sims


def _empty_lane(lane: str) -> dict:
    return {"lane": lane, "chat": [], "study": [], "similarities": []}


def build_report(prose: dict, json_lane: dict) -> str:
    """Assembles the Markdown from two persisted lanes.

    A lane that was never run (or died partway) simply contributes fewer rows —
    `zip` pairs only what both lanes have, and the per-lane summaries below
    still report each lane's own full count. A one-lane report is a legitimate
    output, not an error: the prose lane is free to run and the baseline may be
    waiting on quota.
    """
    parts = []
    pairs = [
        {"question": p["question"], "prose": p, "json": j}
        for p, j in zip(prose["chat"], json_lane["chat"])
    ]
    study_pairs = [
        {"book": p["book"], "item_number": p["item_number"], "prose": p, "json": j}
        for p, j in zip(prose["study"], json_lane["study"])
    ]
    if pairs:
        parts.append(format_report(pairs))
    if study_pairs:
        parts.append(format_study_report(study_pairs))

    parts.append("## Summary\n")
    parts.append(f"- prose lane /chat ({len(prose['chat'])} q): "
                 f"{summarize(prose['chat'])}")
    parts.append(f"- json lane /chat ({len(json_lane['chat'])} q):  "
                 f"{summarize(json_lane['chat'])}")
    parts.append(f"- prose lane style: {style_metrics(prose['chat'])}")
    parts.append(f"- json lane style:  {style_metrics(json_lane['chat'])}")
    parts.append(f"- prose lane /study: {summarize_study(prose['study'])}")
    parts.append(f"- json lane /study:  {summarize_study(json_lane['study'])}")
    if not prose["chat"] or not json_lane["chat"]:
        parts.append(
            "\n> ⚠️ Only one lane has data. These numbers are a comparison or "
            "they are nothing — run the missing lane before drawing a "
            "conclusion."
        )
    parts.append(
        "\n## Answer-to-chunk cosine distribution "
        "(source_min_similarity calibration)\n"
    )
    parts.append(f"- prose lane: {similarity_distribution(prose['similarities'])}")
    parts.append(f"- json lane:  {similarity_distribution(json_lane['similarities'])}")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prose-provider",
        default="ollama",
        help="provider for the prose lane (default: ollama)",
    )
    parser.add_argument(
        "--lane",
        choices=["prose", "json", "both"],
        default="both",
        help="which lane to run; results persist per lane so the two can be "
        "run hours apart (default: both)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="run nothing; rebuild the report from the persisted lane files",
    )
    args = parser.parse_args()

    if not args.report_only:
        if args.lane in ("prose", "both"):
            _run_lane(args.prose_provider, "prose")
        if args.lane in ("json", "both"):
            _run_lane(None, "json")

    prose = load_lane("prose") or _empty_lane("prose")
    json_lane = load_lane("json") or _empty_lane("json")
    print(build_report(prose, json_lane))


if __name__ == "__main__":
    main()
