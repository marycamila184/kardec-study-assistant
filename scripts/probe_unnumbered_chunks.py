"""Measures what dropping unnumbered chunks from retrieval would cost and gain.

Two thirds of O Céu e o Inferno is spirit testimony — first-person accounts,
not doctrinal exposition — and the parser gives those no item number. They are
65% of that book's chunks against 0-12% everywhere else.

They intrude on personal messages, because a testimony is personal language.
Reported on 2026-07-28: "não posso fazer fofoca sobre o meu irmão" retrieved
"não ter sido esquecido entre os meus irmãos espíritas" and produced an answer
about collective calamities. And a chunk with no item number cannot become a
usable citation either — the chip said "cap. VIII" with nothing to look up.

The question this answers is NOT whether they intrude; that is established. It
is what filtering them out would COST. Some of those 856 chunks may be
legitimate exposition the parser failed to number, and the doctrinal half of
Céu e Inferno — the future life, the nature of the penalties — is Kardec that
exists nowhere else in the corpus.

So the risk questions below are the point of the script. If filtering empties
them, the filter is wrong.

Usage:
    uv run python -m scripts.probe_unnumbered_chunks
"""

from src.rag.retriever import retrieve

# Ordinary doctrine. Should be unaffected either way.
NEUTRAL = [
    "o que é o perispírito?",
    "o que Kardec diz sobre a prece?",
    "qual a diferença entre alma e espírito?",
    "o que é a reencarnação?",
]

# Personal phrasing — where testimony language wins on similarity and loses on
# usefulness. This is what the filter is meant to fix.
PERSONAL = [
    "entendi nao posso fazer nenhuma fofoca sobre o meu irmao",
    "estou preocupado com meu pai que está doente",
    "briguei com minha irmã e me sinto mal",
    "penso muito na minha mãe que faleceu",
]

# The risk. These are answered by the DOCTRINAL half of O Céu e o Inferno. If
# the filter empties these, it is taking Kardec with the testimonies.
AT_RISK = [
    "o que acontece com o espírito depois da morte?",
    "existe inferno segundo Kardec?",
    "o que são as penas futuras?",
    "como é a vida dos espíritos no mundo espiritual?",
    "o que Kardec diz sobre a expiação?",
]


def _numbered(chunk: dict) -> bool:
    return str(chunk["metadata"].get("item_number", "")).isdigit()


def _line(chunk: dict) -> str:
    m = chunk["metadata"]
    mark = " " if _numbered(chunk) else "*"
    return f"    {mark} {chunk['distance']:.3f} {m['book'][:26]:<28} item {m.get('item_number')}"


def run(questions: list[str], label: str) -> tuple[int, int, int]:
    print(f"\n=== {label} ===")
    unnumbered = 0
    total = 0
    emptied = 0
    for question in questions:
        chunks = retrieve(question)
        kept = [c for c in chunks if _numbered(c)]
        n_un = len(chunks) - len(kept)
        unnumbered += n_un
        total += len(chunks)
        if chunks and not kept:
            emptied += 1
        flag = "  <-- FICARIA VAZIO" if chunks and not kept else ""
        print(f"\n  {question}{flag}")
        print(f"    sem número: {n_un}/{len(chunks)}")
        for c in chunks[:4]:
            print(_line(c))
    return unnumbered, total, emptied


def main() -> None:
    print("* = chunk sem número de item (sairia do retrieval)")
    a = run(NEUTRAL, "DOUTRINA COMUM — não deveria mudar")
    b = run(PERSONAL, "MENSAGEM PESSOAL — o que o filtro existe para consertar")
    c = run(AT_RISK, "RISCO — doutrina que só o Céu e o Inferno traz")

    print("\n=== resumo ===")
    for label, (un, tot, empty) in [
        ("doutrina comum", a),
        ("pessoal", b),
        ("em risco", c),
    ]:
        share = 100 * un / tot if tot else 0
        print(f"{label:<16} sem número: {un}/{tot} ({share:.0f}%)  esvaziadas: {empty}")


if __name__ == "__main__":
    main()
