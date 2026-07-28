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

from src.rag.premise_check import unsupported_terms
from src.rag.retriever import retrieve

# Ordinary doctrinal questions. Every flag here is a false positive, and enough
# of them means this can never be a gate.
LEGITIMATE = [
    "o que é o perispírito?",
    "qual a diferença entre alma e espírito?",
    "o que Kardec diz sobre a prece?",
    "o que é a reencarnação?",
    "o que acontece depois da morte?",
    "por que existe sofrimento no mundo?",
    "o que são os espíritos protetores?",
    "como funciona a lei de causa e efeito?",
    "o que Kardec fala sobre o perdão?",
    "qual o papel da caridade na doutrina?",
]

# Concepts the works do not carry. Every miss here is the failure reproducing.
OUT_OF_DOCTRINE = [
    "isso influencia o meu ectoplasma e a minha aura",
    "e o duplo etéreo?",
    "o que ele diz sobre a colônia nosso lar",
    "como os chakras se relacionam com o perispírito?",
    "qual a posição sobre cristais energéticos?",
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
    false_positives = run(LEGITIMATE, "LEGÍTIMAS — cada FLAG aqui é falso positivo")
    caught = run(OUT_OF_DOCTRINE, "FORA DA DOUTRINA — cada 'ok' aqui é uma falha")

    print("\n=== resumo ===")
    print(f"falsos positivos: {false_positives}/{len(LEGITIMATE)}")
    print(f"detectadas:       {caught}/{len(OUT_OF_DOCTRINE)}")


if __name__ == "__main__":
    main()
