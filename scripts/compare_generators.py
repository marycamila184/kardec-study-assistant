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

Usage:
    uv run python -m scripts.compare_generators > /tmp/riv-ai-report.md
"""

import argparse

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


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"mean_groundedness": 0.0, "hallucinated_citation_rate": 0.0}
    n = len(rows)
    return {
        "mean_groundedness": sum(r["groundedness"] for r in rows) / n,
        "hallucinated_citation_rate": sum(1 for r in rows if not r["confiavel"]) / n,
    }


def summarize_study(rows: list[dict]) -> dict:
    """The number that tells you whether the marker protocol holds on
    /study: the fraction of study items where generation failed."""
    if not rows:
        return {"study_failure_rate": 0.0}
    n = len(rows)
    return {
        "study_failure_rate": sum(1 for r in rows if r["generation_failed"]) / n,
    }


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
            "**prose lane (riv-ai-v2)**",
            "",
            f"- contexto: {p['prose']['contexto']}",
            f"- conceitos_chave: {p['prose']['conceitos_chave']}",
            f"- generation_failed: {p['prose']['generation_failed']}",
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


def _run_lane(prose_provider: str | None) -> tuple[list[dict], list[dict], list[float]]:
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
        retrieved_ids,
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

    study_rows = []
    for book, item_number in STUDY_ITEMS:
        result = explicar(book, item_number)
        item_chunks = retrieve_by_item(book, item_number)
        contexto = result["contexto"] if result else ""
        study_rows.append(
            {
                "book": book,
                "item_number": item_number,
                "contexto": contexto,
                "conceitos_chave": result["conceitos_chave"] if result else [],
                "generation_failed": result["generation_failed"] if result else True,
                "groundedness": groundedness_score(contexto, item_chunks),
            }
        )

    return rows, study_rows, all_sims


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prose-provider",
        default="ollama",
        help="provider for the prose lane (default: ollama)",
    )
    args = parser.parse_args()

    prose_rows, prose_study, prose_sims = _run_lane(args.prose_provider)
    json_rows, json_study, json_sims = _run_lane(None)

    pairs = [
        {"question": p["question"], "prose": p, "json": j}
        for p, j in zip(prose_rows, json_rows)
    ]
    study_pairs = [
        {"book": p["book"], "item_number": p["item_number"], "prose": p, "json": j}
        for p, j in zip(prose_study, json_study)
    ]

    print(format_report(pairs))
    print(format_study_report(study_pairs))
    print("## Summary\n")
    print(f"- prose lane /chat: {summarize(prose_rows)}")
    print(f"- json lane /chat:  {summarize(json_rows)}")
    print(f"- prose lane /study: {summarize_study(prose_study)}")
    print(f"- json lane /study:  {summarize_study(json_study)}")
    print()
    print(
        "## Answer-to-chunk cosine distribution (source_min_similarity calibration)\n"
    )
    print(f"- prose lane: {similarity_distribution(prose_sims)}")
    print(f"- json lane:  {similarity_distribution(json_sims)}")


if __name__ == "__main__":
    main()
