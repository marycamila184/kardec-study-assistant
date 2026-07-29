"""A/B the response profile: the same question, answered under each shape.

The one thing under test is the profile. Same question, same retrieval, same
model, temperature pinned — so a difference between lanes is attributable to the
profile and nothing else. That is the same discipline compare_generators.py
follows, and for the same reason: two things moving at once explains nothing.

What it reports per lane:

  - quoted spans — how much verbatim source the answer carries. `citation_style:
    inline` is meant to raise this; if it does not, the fragment is not working.
  - inline refs — resolved [fonte N] markers, which are what an inline citation
    is anchored to.
  - prose references — "A Gênese, capítulo X, item 18" written into the text.
    Under `short` this should be near zero, because the interface shows the
    reference beside the answer. Under `full` it is the point.
  - withheld — answers the quotation guard refused. A profile that pushes the
    model to quote more may also push it to quote worse, and this is where that
    would show.

Read as a comparison between lanes, never as absolute numbers.

Costs real tokens: one generation per question per lane.

Usage:
    uv run python -m scripts.compare_profiles
    uv run python -m scripts.compare_profiles --questions 2

See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md
"""

import argparse
import dataclasses
import re

from src.rag.generator import NOT_FOUND_MESSAGE, generate
from src.rag.profile import CHAT_DEFAULT

QUESTIONS = [
    "o que é o perispírito?",
    "qual a diferença entre alma e espírito?",
    "o que Kardec diz sobre a prece?",
]

LANES = {
    "default (chips, short)": CHAT_DEFAULT,
    "inline": dataclasses.replace(CHAT_DEFAULT, citation_style="inline"),
    "inline + full": dataclasses.replace(
        CHAT_DEFAULT, citation_style="inline", citation_precision="full"
    ),
    "none": dataclasses.replace(CHAT_DEFAULT, citation_style="none"),
}

_QUOTED = re.compile(r"[\"“«]([^\"“”«»\n]{20,600})[\"”»]")

# "A Gênese, capítulo X, item 18" and friends — a reference written into the
# prose rather than left to the interface.
_PROSE_REF = re.compile(
    r"(Evangelho|G[êe]nese|Livro dos Esp[íi]ritos|Livro dos M[ée]diuns|C[ée]u e o Inferno)"
    r"[^.\n]{0,60}?(cap[íi]tulo|cap\.)",
    re.IGNORECASE,
)


def measure(question: str, profile) -> dict:
    result = generate(question, [], profile=profile)
    answer = result["answer"]
    return {
        "withheld": answer == NOT_FOUND_MESSAGE and result.get("not_found"),
        "quoted": len(_QUOTED.findall(answer)),
        "inline_refs": len(result.get("inline_refs", [])),
        "prose_refs": len(_PROSE_REF.findall(answer)),
        "chars": len(answer),
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=len(QUESTIONS))
    parser.add_argument("--show", action="store_true", help="print each answer")
    args = parser.parse_args()

    questions = QUESTIONS[: args.questions]
    totals: dict[str, dict] = {}

    for lane, profile in LANES.items():
        rows = [measure(q, profile) for q in questions]
        totals[lane] = {
            "quoted": sum(r["quoted"] for r in rows),
            "inline_refs": sum(r["inline_refs"] for r in rows),
            "prose_refs": sum(r["prose_refs"] for r in rows),
            "withheld": sum(1 for r in rows if r["withheld"]),
            "chars": sum(r["chars"] for r in rows) // len(rows),
        }
        print(f"lane {lane}: done")
        if args.show:
            for q, r in zip(questions, rows):
                print(f"\n  --- {q}\n  {r['answer'][:500]}\n")

    print(f"\n# Profile A/B — {len(questions)} questions per lane\n")
    header = f"{'lane':<24} {'quoted':>7} {'refs':>6} {'prose':>7} {'withheld':>9} {'chars':>7}"
    print(header)
    print("-" * len(header))
    for lane, t in totals.items():
        print(
            f"{lane:<24} {t['quoted']:>7} {t['inline_refs']:>6} "
            f"{t['prose_refs']:>7} {t['withheld']:>9} {t['chars']:>7}"
        )


if __name__ == "__main__":
    main()
