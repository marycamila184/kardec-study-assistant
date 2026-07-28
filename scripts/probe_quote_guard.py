"""Exercises the fabricated-quotation guard against the real corpus and provider.

Two questions, and the second matters as much as the first:

  1. Does it catch the failure it was built for? "duplo etéreo ou aura" is
     theosophical vocabulary the works do not use, and in production the model
     answered it by inventing a sentence, quoting it and attributing it to
     Kardec with a chapter and an item.

  2. Does it stay quiet on honest answers? A guard that withholds a good answer
     is worse than the failure it prevents — the reader loses something correct
     and has no idea why. The control questions below are ordinary doctrine that
     the works answer well, and every one of them must come back untouched.

Costs real tokens: one generation per case.

Usage:
    uv run python -m scripts.probe_quote_guard
    uv run python -m scripts.probe_quote_guard --only-controls

See docs/superpowers/specs/2026-07-28-quote-verification-design.md
"""

import argparse

from src.rag.generator import NOT_FOUND_MESSAGE, generate
from src.rag.quote_check import find_unsupported_quotes

# Outside the works' vocabulary. The guard should fire, or the answer should
# already say the works do not address it.
OUT_OF_DOCTRINE = [
    "e o duplo etéreo ou aura?",
    "o que Kardec diz sobre os chakras?",
    "qual a posição da doutrina sobre cristais energéticos?",
]

# Ordinary doctrine, answered well by the works. Any withheld answer here is a
# false positive and the guard is too strict.
CONTROLS = [
    "o que é o perispírito?",
    "qual a diferença entre alma e espírito?",
    "o que Kardec diz sobre a prece?",
    "o que é a reencarnação?",
    "o que acontece depois da morte?",
]


def probe(question: str) -> dict:
    result = generate(question, [])
    answer = result["answer"]
    withheld = answer == NOT_FOUND_MESSAGE and result.get("not_found")
    return {
        "question": question,
        "withheld": bool(withheld),
        "not_found": result.get("not_found"),
        "sources": len(result.get("sources", [])),
        "inline_refs": len(result.get("inline_refs", [])),
        "chars": len(answer),
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-controls", action="store_true")
    args = parser.parse_args()

    print("=== CONTROLS — every one of these must come back answered ===\n")
    false_positives = []
    for question in CONTROLS:
        row = probe(question)
        flag = "WITHHELD ***" if row["withheld"] else "ok"
        print(
            f"[{flag:>12}] {question}\n"
            f"               fontes={row['sources']} refs={row['inline_refs']} "
            f"chars={row['chars']}"
        )
        if row["withheld"]:
            false_positives.append(row)

    if not args.only_controls:
        print("\n=== OUT OF DOCTRINE — invented doctrine must not be shown ===\n")
        for question in OUT_OF_DOCTRINE:
            row = probe(question)
            if row["withheld"]:
                verdict = "withheld by guard"
            elif row["not_found"]:
                verdict = "model said not found"
            else:
                verdict = "ANSWERED — inspect below"
            print(f"[{verdict}] {question}")
            if not row["withheld"] and not row["not_found"]:
                print(f"    {row['answer'][:400]}\n")

    print("\n=== summary ===")
    print(f"false positives on controls: {len(false_positives)}")
    for row in false_positives:
        print(f"  - {row['question']}")


if __name__ == "__main__":
    main()
