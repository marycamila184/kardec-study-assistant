"""Measures the premise check before anyone decides what it should do.

The signal: a question introduces a term the retrieved passages never use, and
the answer explains it anyway. That was the 2026-07-28 failure — "ectoplasma"
and "aura" explained as doctrine because the premise was embedded in the
question rather than asked about.

The question this script answers is not "does it catch the bad ones" — it does,
by construction. It is **how often it fires on good ones**, because that decides
whether it can ever gate an answer. This project has twice shipped a guard tuned
by reasoning rather than evidence, and both times it withheld correct answers.

Usage:
    uv run python -m scripts.probe_premise_check
"""

import json
import pathlib

from src.rag.premise_check import unsupported_terms
from src.rag.retriever import retrieve


# Real study questions, taken from the curated learning paths in data/paths/.
# Their labels ARE the works' own subject lines, hand-reviewed — a far better
# sample than anything invented to test with, because nobody wrote them with
# this check in mind. Every flag here is a false positive.
def legitimate_questions() -> list[str]:
    labels: list[str] = []
    for path in sorted(pathlib.Path("data/paths").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data.get("steps", []):
            label = (step.get("label") or "").strip()
            if label and label not in labels:
                labels.append(label)
    return labels


# Concepts the works do not carry — the failures reported from real use, plus
# neighbouring ones from the same families (theosophy, later spiritist authors,
# new age). Every miss here is the failure reproducing.
OUT_OF_DOCTRINE = [
    "isso influencia o meu ectoplasma e a minha aura",
    "e o duplo etéreo?",
    "o que ele diz sobre a colônia nosso lar",
    "como os chakras se relacionam com o perispírito?",
    "qual a posição sobre cristais energéticos?",
    "o que Kardec fala sobre apometria?",
    "e sobre os cordões energéticos entre as pessoas?",
    "como funciona o carma segundo Kardec?",
    "o que ele diz sobre os registros akáshicos?",
    "qual a visão sobre terapia de vidas passadas?",
]


def run(questions: list[str], label: str) -> int:
    print(f"\n=== {label} ===\n")
    fired = 0
    for question in questions:
        try:
            chunks = retrieve(question)
        except Exception as err:  # noqa: BLE001
            print(f"  [retrieve failed] {question}: {err}")
            continue
        terms = unsupported_terms(question, chunks)
        if terms:
            fired += 1
            print(f"  [FLAG] {question}\n         termos ausentes: {terms}")
        else:
            print(f"  [ ok ] {question}")
    return fired


def main() -> None:
    legitimate = legitimate_questions()
    false_positives = run(legitimate, "LEGÍTIMAS — cada FLAG aqui é falso positivo")
    caught = run(OUT_OF_DOCTRINE, "FORA DA DOUTRINA — cada 'ok' aqui é uma falha")

    print("\n=== resumo ===")
    print(f"falsos positivos: {false_positives}/{len(legitimate)}")
    print(f"detectadas:       {caught}/{len(OUT_OF_DOCTRINE)}")


if __name__ == "__main__":
    main()
