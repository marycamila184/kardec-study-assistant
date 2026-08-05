"""Does a continuous overlap measure separate an invention from a re-inflected
quotation, where the binary anchor does not?

`find_unsupported_quotes` discards a whole answer when no run of
MIN_QUOTED_WORDS consecutive words appears in the retrieved text. On
2026-08-04 that fired on:

    a duração das penas depende dos esforços do culpado

against a work that says "…a duração das penas **dependa** dos esforços do
culpado". One verb, moved from subjunctive to indicative to fit the model's own
sentence. Nine words, four possible 6-word windows, the altered word inside all
four — so nothing anchored and a correct answer was replaced with "não
encontrei", printed underneath the passage that answered the question.

This script measures whether **bigram coverage** — the fraction of the
quotation's adjacent word pairs present in the haystack — separates the two
classes that the anchor conflates. It decides nothing on its own: the gate is
in the design doc, and it is that the distributions must not overlap.

    docs/superpowers/specs/2026-08-04-quote-check-false-positive-design.md

Usage:
    bq query --use_legacy_sql=false --format=json --max_rows=500 '
      SELECT timestamp, jsonPayload.turn_id, jsonPayload.question,
             jsonPayload.answer, jsonPayload.not_found, jsonPayload.retrieved
      FROM `dialogando-doutrina.kardec_logs.run_googleapis_com_stdout`
      WHERE jsonPayload.event = "chat_turn" ORDER BY timestamp' > turns.json

    PYTHONPATH=. uv run python -m scripts.measure_quote_guard turns.json
"""

import json
import sys
from statistics import median

from src.rag.quote_check import (
    _QUOTED,
    MIN_QUOTED_WORDS,
    _has_anchor,
    _normalise,
    _words,
)
from src.rag.retriever import prompt_text, retrieve_by_item

# The quotations production withheld answers over, from the Cloud Logging
# `stderr` lines. They are not recoverable from the turn log: a withheld turn
# records NOT_FOUND_MESSAGE as its answer, so the text that caused the
# withholding is gone. That is itself a finding — see §5 of the design.
WITHHELD_QUOTES = [
    ("2026-08-04T14:20:45", "mais ou menos felizes, conforme seus méritos"),
    ("2026-08-04T14:14:22", "a duração das penas depende dos esforços do culpado"),
    ("2026-08-04T14:11:35", "a duração das penas depende dos esforços do culpado"),
    ("2026-08-04T14:10:46", "a duração das penas depende dos esforços do culpado"),
    ("2026-07-31T03:13:01", "a fé cega é a fé da ignorância"),
    (
        "2026-07-31T03:13:01",
        "a razão é a luz que Deus deu ao homem para que ele pudesse distinguir o bem do mal",
    ),
    (
        "2026-07-31T03:13:01",
        "a fé é a adesão do espírito às coisas que ele não vê, mas que a razão lhe diz que existem",
    ),
]

# Positive control. The first is the real fabrication this guard was built for
# (2026-07-28, "duplo etéreo"); the rest are written in the same shape —
# doctrine-flavoured sentences about notions the works do not carry. If bigram
# coverage cannot tell these from the list above, it is not a usable metric.
INVENTED = [
    "o duplo etéreo é uma espécie de envoltório fluídico que envolve o corpo "
    "físico e é uma extensão do perispírito",
    "a glândula pineal é o órgão pelo qual o Espírito governa as vibrações do "
    "corpo astral durante o sono",
    "os chakras distribuem a energia vital pelos sete centros de força do "
    "perispírito encarnado",
    "o carma acumulado em vidas passadas determina de forma inalterável a "
    "posição social de cada encarnação",
]


def bigram_coverage(words: list[str], haystack_bigrams: set[str]) -> float:
    """Fraction of the quotation's adjacent word pairs present in the haystack.

    Bigrams rather than the longest literal run, because the run is hostage to
    *where* the alteration falls: change the middle word of a nine-word
    quotation and the longest run halves; change the last and it barely moves.
    Coverage counts the damage, not its position.
    """
    if len(words) < 2:
        return 0.0
    pairs = [f"{a} {b}" for a, b in zip(words, words[1:])]
    return sum(p in haystack_bigrams for p in pairs) / len(pairs)


def bigrams_of(text: str) -> set[str]:
    w = text.split()
    return {f"{a} {b}" for a, b in zip(w, w[1:])}


def haystack_for(retrieved: list[dict]) -> str:
    """Rebuild what the model was shown, from the log's chunk references.

    The turn log records `book`/`chapter`/`item`/`distance`, never the text, so
    the passages are fetched back out of the index. A reference that no longer
    resolves is skipped and counted — an index rebuilt since the turn was
    logged is a real possibility, and silently scoring against a shorter
    haystack would manufacture false positives in the measurement itself.

    **The log's `chapter` is the display title, not the machine id.**
    `retrieve_by_item`'s `chapter` argument filters the `chapter` metadata
    field ("CAPÍTULO XXVIII"), while the log carries `chapter_title`
    ("COLETÂNEA DE PRECES ESPÍRITAS"). Passing one where the other is expected
    matches nothing, silently — the first run of this script scored every
    class at 0.00 for exactly that reason. So the item is fetched unfiltered
    and narrowed here, on the field the log actually holds.
    """
    parts, missing = [], 0
    for r in retrieved:
        try:
            chunks = retrieve_by_item(r["book"], str(r["item"]))
        except Exception:
            chunks = []
        wanted = r.get("chapter")
        if wanted:
            narrowed = [
                c for c in chunks if c["metadata"].get("chapter_title") == wanted
            ]
            # Numbering restarts per chapter in Evangelho, Céu e Inferno and
            # Gênese, so an unnarrowed list can hold a different work's item.
            # Keep the narrowing only when it found something.
            chunks = narrowed or chunks
        if not chunks:
            missing += 1
            continue
        parts.extend(_normalise(prompt_text(c)) for c in chunks)
    return " ".join(parts), missing


def quotes_in(answer: str) -> list[str]:
    out = []
    for m in _QUOTED.finditer(answer or ""):
        if len(_words(m.group(1))) >= MIN_QUOTED_WORDS:
            out.append(m.group(1).strip())
    return out


def describe(label: str, scores: list[float]) -> None:
    if not scores:
        print(f"  {label:34} (nenhum caso)")
        return
    s = sorted(scores)
    print(
        f"  {label:34} n={len(s):3d}  min={s[0]:.2f}  "
        f"mediana={median(s):.2f}  max={s[-1]:.2f}"
    )


def main(path: str) -> None:
    turns = json.load(open(path))
    is_nf = lambda t: str(t["not_found"]).lower() == "true"  # noqa: E731

    passed = [t for t in turns if not is_nf(t)]
    withheld = [t for t in turns if is_nf(t) and t["retrieved"]]
    empty = [t for t in turns if is_nf(t) and not t["retrieved"]]

    print(f"turnos: {len(turns)}")
    print(f"  passaram                     : {len(passed)}")
    print(f"  retidos pelo quote-check     : {len(withheld)}")
    print(f"  'não encontrei' sem chunks   : {len(empty)}")
    print()

    # ---- negative class: quotations the guard accepted, in production -------
    accepted, anchored_but_low, total_missing = [], 0, 0
    for t in passed:
        qs = quotes_in(t["answer"])
        if not qs:
            continue
        hay, missing = haystack_for(t["retrieved"])
        total_missing += missing
        bg = bigrams_of(hay)
        for q in qs:
            w = _words(q)
            cov = bigram_coverage(w, bg)
            accepted.append(cov)
            if _has_anchor(w, hay) and cov < 0.9:
                anchored_but_low += 1

    # ---- the false positives, against their own turns' haystacks -----------
    fp = []
    for ts, quote in WITHHELD_QUOTES:
        turn = (
            min(withheld, key=lambda t: abs_ts_delta(t["timestamp"], ts))
            if withheld
            else None
        )
        if turn is None:
            continue
        hay, missing = haystack_for(turn["retrieved"])
        total_missing += missing
        bg = bigrams_of(hay)
        w = _words(quote)
        fp.append((quote, bigram_coverage(w, bg), _has_anchor(w, hay)))

    # ---- positive control: inventions, against every withheld haystack ------
    inv = []
    hays = [bigrams_of(haystack_for(t["retrieved"])[0]) for t in withheld] or [set()]
    for quote in INVENTED:
        w = _words(quote)
        inv.append((quote, max(bigram_coverage(w, bg) for bg in hays)))

    print("COBERTURA DE BIGRAMAS")
    describe("aceitas em produção", accepted)
    describe("retidas (falsos positivos?)", [c for _, c, _ in fp])
    describe("inventadas (controle)", [c for _, c in inv])
    print()

    print("as retidas, uma a uma:")
    for quote, cov, anchor in sorted(fp, key=lambda r: -r[1]):
        print(f"  cov={cov:.2f}  ancora={anchor}  {quote[:72]}")
    print()
    print("o controle de invenção:")
    for quote, cov in sorted(inv, key=lambda r: -r[1]):
        print(f"  cov={cov:.2f}  {quote[:72]}")
    print()

    fp_scores = [c for _, c, _ in fp]
    inv_scores = [c for _, c in inv]
    if fp_scores and inv_scores:
        gap_lo, gap_hi = max(inv_scores), min(fp_scores)
        print(
            f"PORTÃO: invenções vão até {gap_lo:.2f}; retidas começam em {gap_hi:.2f}"
        )
        print(
            "  -> as classes SEPARAM. Um corte cabe na folga."
            if gap_lo < gap_hi
            else "  -> as classes SE SOBREPÕEM. A métrica não serve; §3.2 não sai."
        )
    if accepted:
        print(f"  aceitas em produção nunca abaixo de {min(accepted):.2f}")
    if total_missing:
        print(f"  (chunks não resolvidos no índice atual: {total_missing})")
    if anchored_but_low:
        print(f"  (ancoraram mas com cobertura <0.90: {anchored_but_low})")


def abs_ts_delta(a: str, b: str) -> float:
    """Seconds between two ISO-ish timestamps, compared on the shared prefix."""
    from datetime import datetime

    fmt = "%Y-%m-%dT%H:%M:%S"
    pa = datetime.strptime(a[:19].replace(" ", "T"), fmt)
    pb = datetime.strptime(b[:19].replace(" ", "T"), fmt)
    return abs((pa - pb).total_seconds())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "turns.json")
