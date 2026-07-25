"""Side-by-side comparison of the prose lane against the current provider.

Run each question through both lanes and report, per lane, the two numbers that
decide whether the swap is an improvement:

  - mean groundedness: how close answers stay to their retrieved passages
  - hallucinated-citation rate: how often the model cites outside that set

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


def format_report(pairs: list[dict]) -> str:
    lines = ["# RIV AI v2 vs current provider", ""]
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


def _run_lane(prose_provider: str | None) -> list[dict]:
    """Runs every question with the prose lane pointed at `prose_provider`.

    `settings` is a module-level singleton built at import time, so setting an
    env var here would be read too late. Mutate the setting directly and clear
    the client cache so the next call rebuilds against the new provider.
    """
    from src.core.config import settings
    from src.rag import llm_client
    from src.rag.citations import (
        extract_model_citations,
        retrieved_ids,
        validate_model_citations,
    )
    from src.rag.generator import generate
    from src.rag.groundedness import groundedness_score
    from src.rag.retriever import retrieve

    settings.prose_provider = prose_provider
    llm_client._clients.clear()

    rows = []
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
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prose-provider",
        default="ollama",
        help="provider for the prose lane (default: ollama)",
    )
    args = parser.parse_args()

    prose_rows = _run_lane(args.prose_provider)
    json_rows = _run_lane(None)

    pairs = [
        {"question": p["question"], "prose": p, "json": j}
        for p, j in zip(prose_rows, json_rows)
    ]
    print(format_report(pairs))
    print("## Summary\n")
    print(f"- prose lane: {summarize(prose_rows)}")
    print(f"- json lane:  {summarize(json_rows)}")


if __name__ == "__main__":
    main()
