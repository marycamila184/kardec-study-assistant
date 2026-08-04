"""A/B the one question `2026-08-03-parent-context-expansion-design` is gated on:
does giving the model the ITEM around a hit change the answer, and for the better?

`/chat` builds its prompt from the ≤800-char subchunks that won semantic search.
Half the corpus's numbered items are more than one of those, and 30% of non-first
subchunks are cut mid-paragraph — so half the time the model reasons on a
fragment. `expand_to_item` widens each hit to the item around it, capped at 3000
chars, and leaves `content` alone so the source chip still shows what won.

Two lanes, one dimension:

  baseline   settings.expand_to_item = False  (production today)
  expanded   settings.expand_to_item = True

Everything else is pinned. Temperature is 0 by default for the reason
compare_generators pins it: unpinned, a retrieval difference and sampling noise
are indistinguishable. That is wrong for production and right for an A/B.

**The six numbers, and what each one can decide.**

1. `answer_similarity` — cosine between the two lanes' answers, per case. This
   comes first because it is the cheapest possible negative result: if the
   answers are all but identical, the feature is inert and the other five
   numbers are a waste of tokens to read.
2. `mean_groundedness` — the dilution question, measured instead of argued.
   Computed against the SAME reference chunks in both lanes (see `_reference`),
   because a lane scored against its own wider text would be scoring the ruler.
3. `hallucinated_citation_rate` — already the harness's standard metric.
4. `withheld` — answers lost to `not_found`. The regression alarm for the
   quote-guard invariant: expansion widens what the model may quote, so a
   haystack still built from `content` would read a correct quotation from a
   neighbouring subchunk as fabrication and discard the whole answer. **Must be
   zero, and a non-zero here settles the run on its own.**
5. `by_shape` — the same metrics split by whether the top hit was a fragment
   (multi-subchunk item) or a whole item. The feature only claims to help the
   first group; if the gains do not concentrate there, the mechanism is not what
   this spec says it is, whatever the aggregate looks like.
6. `mean_prompt_chars` / `mean_seconds` — the ~3.3× estimate, verified.

Lanes persist to `logs/expansion-<lane>.json` after every case, so a provider
quota error mid-run costs the remaining cases and never the finished ones — the
lesson compare_generators paid for on 2026-07-25.

Usage:
    uv run python -m scripts.compare_expansion                  # both lanes
    uv run python -m scripts.compare_expansion --lanes baseline # one lane
    uv run python -m scripts.compare_expansion --report-only    # re-read logs
    uv run python -m scripts.compare_expansion --limit 8        # smoke run
"""

import argparse
import json
import os
import time
from contextlib import contextmanager
from unittest.mock import patch

from scripts.compare_generators import CASES

LANE_DIR = "logs"
LANES = ("baseline", "expanded")


def lane_path(lane: str) -> str:
    return os.path.join(LANE_DIR, f"expansion-{lane}.json")


def save_lane(lane: str, rows: list[dict]) -> None:
    """Written to a temp file and renamed, so a crash mid-write cannot leave a
    truncated file that later reads as valid-but-short."""
    os.makedirs(LANE_DIR, exist_ok=True)
    tmp = lane_path(lane) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"lane": lane, "rows": rows}, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, lane_path(lane))


def load_lane(lane: str) -> list[dict] | None:
    try:
        with open(lane_path(lane), encoding="utf-8") as fh:
            return json.load(fh)["rows"]
    except FileNotFoundError:
        return None


def _recording_prose_completion(
    temperature: float | None, prompt_chars: list[int], finish_reasons: list[str | None]
):
    """Stands in for `generator.prose_completion`, pinning sampling and recording
    the prompt size.

    Prompt chars cannot travel out of `generator.generate` — it returns the
    answer string — and the whole point of measuring them is that they are the
    cost of this change. Reading them from the harness's own stand-in is the
    smallest way to get them without a production signature growing a parameter
    that exists only for a test.
    """
    from src.core.config import settings
    from src.rag.llm_client import get_client

    def shim(system: str, messages: list[dict], max_tokens: int = 1024):
        payload = [{"role": "system", "content": system}] + messages
        prompt_chars.append(sum(len(m["content"]) for m in payload))
        kwargs = {} if temperature is None else {"temperature": temperature}
        response = get_client("prose").chat.completions.create(
            model=settings.resolved_prose_model,
            max_tokens=max_tokens,
            messages=payload,
            **kwargs,
        )
        finish_reasons.append(response.choices[0].finish_reason)
        return response.choices[0].message.content

    return shim


@contextmanager
def _lane_settings(lane: str):
    """`expand_to_item` is the only thing that moves between lanes.

    The prose lane is forced off for the reason compare_generators forces it off:
    a retrieval A/B run across two models could never attribute a difference to
    either one. Restored on the way out so a `--lanes both` run does not leak
    the first lane's settings into the second.
    """
    from src.core.config import settings
    from src.rag import llm_client

    before = (settings.expand_to_item, settings.prose_provider)
    settings.expand_to_item = lane == "expanded"
    settings.prose_provider = None
    llm_client._clients.clear()
    try:
        yield
    finally:
        settings.expand_to_item, settings.prose_provider = before
        llm_client._clients.clear()


def _reference(question: str) -> list[dict]:
    """The chunks both lanes are scored against.

    Retrieved once, from the unexpanded path, and reused for every lane.
    Groundedness measures how close an answer sits to its passages; letting the
    expanded lane be scored against its own wider text would move the ruler with
    the thing being measured, and a lane cannot be allowed to score better
    merely by having been given more text to resemble.
    """
    from src.rag.retriever import retrieve

    return retrieve(question)


def _is_fragment(chunks: list[dict]) -> bool:
    """Whether the top hit is one piece of a longer item — the subset this
    feature claims to help. `total_subchunks` is the same signal `expand_to_item`
    itself branches on, so the split cannot drift from the behaviour."""
    if not chunks:
        return False
    return (chunks[0]["metadata"].get("total_subchunks") or 1) > 1


def run_lane(lane: str, cases: list[dict], temperature: float | None) -> list[dict]:
    from src.rag import generator
    from src.rag.citations import (
        extract_model_citations,
        retrieved_ids,
        validate_model_citations,
    )
    from src.rag.groundedness import groundedness_score

    rows: list[dict] = []
    with _lane_settings(lane):
        for case in cases:
            reference = _reference(case["question"])
            prompt_chars: list[int] = []
            finish_reasons: list[str | None] = []
            shim = _recording_prose_completion(
                temperature, prompt_chars, finish_reasons
            )
            started = time.monotonic()
            with patch("src.rag.generator.prose_completion", shim):
                result = generator.generate(case["question"], case["history"])
            elapsed = time.monotonic() - started

            report = validate_model_citations(
                extract_model_citations(result["answer"]), retrieved_ids(reference)
            )
            rows.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "answer": result["answer"],
                    "not_found": bool(result.get("not_found")),
                    "n_sources": len(result.get("sources") or []),
                    "groundedness": groundedness_score(result["answer"], reference),
                    "confiavel": report["confiavel"],
                    "is_fragment": _is_fragment(reference),
                    # None when the turn short-circuited before any LLM call —
                    # smalltalk and the crisis exit never reach prose_completion.
                    "prompt_chars": prompt_chars[-1] if prompt_chars else None,
                    "finish_reason": finish_reasons[-1] if finish_reasons else None,
                    "seconds": elapsed,
                }
            )
            save_lane(lane, rows)
    return rows


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "mean_groundedness": _mean([r["groundedness"] for r in rows]),
        "hallucinated_citation_rate": (
            sum(1 for r in rows if not r["confiavel"]) / len(rows) if rows else 0.0
        ),
        "withheld": sum(1 for r in rows if r["not_found"]),
        "mean_prompt_chars": _mean(
            [r["prompt_chars"] for r in rows if r["prompt_chars"] is not None]
        ),
        "mean_seconds": _mean([r["seconds"] for r in rows]),
        "mean_sources": _mean([r["n_sources"] for r in rows]),
        "truncados": sum(1 for r in rows if r["finish_reason"] not in (None, "stop")),
    }


def answer_similarities(lanes: dict[str, list[dict]]) -> dict[str, float]:
    """Per-case cosine between the two lanes' answers.

    Metric 1, and the one that can end the run early: answers that barely move
    mean the extra context was not used, and nothing else here is worth reading.
    """
    from src.ingestion.embeddings import encode
    from src.rag.groundedness import _cosine

    baseline = {r["id"]: r["answer"] for r in lanes.get("baseline", [])}
    expanded = {r["id"]: r["answer"] for r in lanes.get("expanded", [])}
    shared = [cid for cid in baseline if cid in expanded]
    if not shared:
        return {}
    vectors = encode([baseline[c] for c in shared] + [expanded[c] for c in shared])
    half = len(shared)
    return {cid: _cosine(vectors[i], vectors[half + i]) for i, cid in enumerate(shared)}


def format_report(lanes: dict[str, list[dict]], sims: dict[str, float]) -> str:
    lines = ["# /chat — expansão do chunk para o item", ""]

    if sims:
        ordered = sorted(sims.items(), key=lambda kv: kv[1])
        lines += [
            "## 1. As respostas mudaram?",
            "",
            f"Cosseno médio entre as vias: **{_mean(list(sims.values())):.3f}** "
            f"(1.000 = idênticas). {sum(1 for v in sims.values() if v > 0.98)} de "
            f"{len(sims)} casos acima de 0.98.",
            "",
            "| caso | cosseno |",
            "|---|---|",
        ]
        lines += [f"| {cid} | {value:.3f} |" for cid, value in ordered]
        lines.append("")

    lines += ["## 2-4, 6. Por via", "", "| métrica | " + " | ".join(lanes) + " |"]
    lines.append("|---|" + "---|" * len(lanes))
    summaries = {name: summarize(rows) for name, rows in lanes.items()}
    for key in (
        "n",
        "mean_groundedness",
        "hallucinated_citation_rate",
        "withheld",
        "mean_sources",
        "mean_prompt_chars",
        "mean_seconds",
        "truncados",
    ):
        cells = []
        for name in lanes:
            value = summaries[name][key]
            cells.append(f"{value:.3f}" if isinstance(value, float) else str(value))
        lines.append(f"| {key} | " + " | ".join(cells) + " |")
    lines.append("")

    lines += [
        "## 5. Por formato do trecho de topo",
        "",
        "`fragmento` = o trecho que venceu é um pedaço de um item maior — o "
        "subconjunto que esta mudança diz ajudar. Se o ganho não se concentra "
        "aqui, o mecanismo não é o que a spec afirma.",
        "",
        "| via | formato | n | groundedness | retidas |",
        "|---|---|---|---|---|",
    ]
    for name, rows in lanes.items():
        for label, subset in (
            ("fragmento", [r for r in rows if r["is_fragment"]]),
            ("item inteiro", [r for r in rows if not r["is_fragment"]]),
        ):
            if not subset:
                continue
            s = summarize(subset)
            lines.append(
                f"| {name} | {label} | {s['n']} | {s['mean_groundedness']:.3f} "
                f"| {s['withheld']} |"
            )
    lines.append("")

    withheld = [
        (name, r["id"]) for name, rows in lanes.items() for r in rows if r["not_found"]
    ]
    if withheld:
        lines += [
            "## ⚠️ Respostas retidas",
            "",
            "Uma retenção que só aparece na via expandida é o alarme da guarda de "
            "citação: o modelo leu o item inteiro e citou um subtrecho vizinho "
            "corretamente, e um palheiro montado só com `content` chamaria isso "
            "de invenção — descartando a resposta inteira.",
            "",
        ]
        lines += [f"- `{name}` — {cid}" for name, cid in withheld]
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lanes", default=",".join(LANES))
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="sampling temperature; pass -1 to restore production sampling",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="run only the first N cases"
    )
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    names = [n.strip() for n in args.lanes.split(",") if n.strip()]
    unknown = [n for n in names if n not in LANES]
    if unknown:
        parser.error(f"unknown lane(s): {', '.join(unknown)}; expected {LANES}")

    cases = CASES[: args.limit] if args.limit else CASES
    temperature = None if args.temperature < 0 else args.temperature

    lanes: dict[str, list[dict]] = {}
    for name in names:
        if args.report_only:
            rows = load_lane(name)
            if rows is None:
                parser.error(f"no persisted run for lane {name}")
        else:
            print(f"→ via {name} ({len(cases)} casos)", flush=True)
            rows = run_lane(name, cases, temperature)
        lanes[name] = rows

    print(format_report(lanes, answer_similarities(lanes)))


if __name__ == "__main__":
    main()
