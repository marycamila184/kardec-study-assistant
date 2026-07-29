"""Measures whether /study's inline grounding markers can be trusted.

The validation in `inline_refs.py` guarantees that a *fabricated* marker never
reaches a reader — it is dropped in code. That guarantee is unconditional and
needs no measurement. What needs measuring is everything it cannot fix:

  - **marker rate** — does the model emit markers at all? A rule the model
    ignores produces a technically-correct answer with no references in it,
    which looks identical to success from the code's point of view.
  - **invented rate** — how often it names an item that was not retrieved. Each
    one is silently dropped, so this number is invisible in production and only
    appears here. A model that invents constantly is being carried by the
    validation rather than following the rule, and would fail the moment the
    validation were relaxed.
  - **coverage** — of the chapter items actually available, how many get cited.
  - **placement** — whether markers land inside the prose or get clumped at the
    end, which would defeat the point of being inline.

Read as a comparison between lanes, never as absolute thresholds. The only hard
line is `invented_reaching_reader`, which must be 0.00 in every lane: that is
the invariant, and a non-zero value means the validation itself is broken.

Like the other comparison scripts: one lane per model, each persisted to
`logs/markers-<lane>.json` after every case, so a run that dies mid-way keeps
what it produced.

Usage:
    uv run python -m scripts.eval_inline_markers --models together:meta-llama/Llama-3.3-70B-Instruct-Turbo
    uv run python -m scripts.eval_inline_markers --report-only

See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
"""

import argparse
import json
import os
import re

from src.core.config import settings
from src.rag import explicador
from src.rag.explicador_prompt import parse_explicador_json
from src.rag.inline_refs import _ITEM_MARKER, extract_item_refs

# Evangelho items, because chapter commentary — the thing markers point at — is
# Evangelho-only by construction (see chapter_commentary in retriever.py).
# Chosen to span chapters with plenty of sibling commentary and chapters with
# little, since "no items available" and "many available" are different tests.
CASES = [
    {
        "id": "chamados-14",
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO XVIII",
        "item_number": "14",
    },
    {
        "id": "caridade-4",
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO XV",
        "item_number": "4",
    },
    {
        "id": "bem-aventurados-2",
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO IX",
        "item_number": "2",
    },
    {
        "id": "prece-4",
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO XXVII",
        "item_number": "4",
    },
    # A book with no chapter commentary at all: the correct behaviour is zero
    # markers, and a model that emits them anyway is inventing.
    {
        "id": "le-132-sem-comentario",
        "book": "O Livro dos Espíritos",
        "chapter": None,
        "item_number": "132",
    },
]

LOG_DIR = "logs"


def _measure(case: dict, raw_contexto: str, chapter_context: list[dict]) -> dict:
    """One case's numbers, computed from the model's raw output — before
    validation strips anything, which is the only place invented markers are
    still visible."""
    written = [m.group(1) for m in _ITEM_MARKER.finditer(raw_contexto)]
    available = {str(c["item_number"]) for c in chapter_context}
    invented = [n for n in written if n not in available]

    clean, refs = extract_item_refs(raw_contexto, chapter_context)

    # Placement: a marker in the last fifth of the text is effectively a
    # trailer, not an inline reference.
    tail_start = len(clean) * 4 // 5
    in_tail = sum(1 for r in refs if r["position"] >= tail_start)

    return {
        "id": case["id"],
        "markers_written": len(written),
        "invented": len(invented),
        "invented_numbers": invented,
        "available": len(available),
        "distinct_cited": len({r["item_number"] for r in refs}),
        "refs_resolved": len(refs),
        "refs_in_tail": in_tail,
        "chars": len(clean),
        # The invariant, recomputed from the output the reader would see.
        "markers_reaching_reader": len(_ITEM_MARKER.findall(clean)),
    }


def summarize(rows: list[dict]) -> dict:
    total_written = sum(r["markers_written"] for r in rows)
    total_available = sum(r["available"] for r in rows)
    with_any = sum(1 for r in rows if r["markers_written"])

    return {
        "cases": len(rows),
        "cases_with_any_marker": f"{with_any}/{len(rows)}",
        "markers_per_answer": round(total_written / len(rows), 2) if rows else 0.0,
        "invented_rate": (
            round(sum(r["invented"] for r in rows) / total_written, 3)
            if total_written
            else 0.0
        ),
        "coverage": (
            round(sum(r["distinct_cited"] for r in rows) / total_available, 3)
            if total_available
            else 0.0
        ),
        "tail_clumping": (
            round(
                sum(r["refs_in_tail"] for r in rows)
                / max(1, sum(r["refs_resolved"] for r in rows)),
                3,
            )
        ),
        # Must be 0.00. Anything else means the validation is broken, not the model.
        "invented_reaching_reader": sum(r["markers_reaching_reader"] for r in rows),
    }


def _lane_path(lane: str) -> str:
    return os.path.join(LOG_DIR, f"markers-{re.sub(r'[/:]', '-', lane)}.json")


def _save(lane: str, rows: list[dict]) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(_lane_path(lane), "w", encoding="utf-8") as f:
        json.dump({"lane": lane, "rows": rows}, f, ensure_ascii=False, indent=2)


def _load(lane: str) -> dict | None:
    try:
        with open(_lane_path(lane), "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def _model_for(lane: str) -> str:
    """The lane name is a provider:model pair, or "default" — which means
    whatever the current configuration resolves to, not a model called
    "default". Passing the literal lane name is a 404 from the provider."""
    if lane == "default":
        return settings.resolved_chat_model
    return lane.split(":", 1)[1] if ":" in lane else lane


def run_lane(lane: str) -> list[dict]:
    rows: list[dict] = []
    for case in CASES:
        ctx = explicador.prepare_study(
            case["book"], case["item_number"], case["chapter"]
        )
        if ctx is None:
            print(f"  {case['id']}: item not found, skipped")
            continue

        response = explicador.get_client("json").chat.completions.create(
            model=_model_for(lane),
            max_tokens=1024,
            messages=[{"role": "system", "content": ctx["system"]}] + ctx["messages"],
            temperature=0,
        )
        raw_contexto, _, _ = parse_explicador_json(response.choices[0].message.content)
        row = _measure(case, raw_contexto, explicador.build_chapter_context(ctx))
        rows.append(row)
        # Written after every case: a run that dies keeps what it produced.
        _save(lane, rows)
        print(
            f"  {case['id']}: {row['markers_written']} markers, {row['invented']} invented"
        )
    return rows


def format_report(lanes: dict[str, list[dict]]) -> str:
    out = ["# Inline marker evaluation\n"]
    for lane, rows in lanes.items():
        if not rows:
            continue
        s = summarize(rows)
        out.append(f"\n## {lane}\n")
        for key, value in s.items():
            out.append(f"- **{key}**: {value}")
        worst = [r for r in rows if r["invented"]]
        if worst:
            out.append("\nInvented references (dropped before display):\n")
            for r in worst:
                out.append(f"- `{r['id']}`: {', '.join(r['invented_numbers'])}")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", help="comma-separated provider:model lanes")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    lane_names = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    if not lane_names:
        lane_names = ["default"]

    lanes: dict[str, list[dict]] = {}
    for lane in lane_names:
        if args.report_only:
            saved = _load(lane)
            lanes[lane] = saved["rows"] if saved else []
        else:
            print(f"lane {lane}:")
            lanes[lane] = run_lane(lane)

    print(format_report(lanes))


if __name__ == "__main__":
    main()
