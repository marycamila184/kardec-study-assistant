"""Side-by-side comparison of the two lanes on `/reflect` — the mode the prose
lane deliberately does NOT serve.

`scripts/compare_generators.py` covers /chat and /study, the two modes the
2026-07-24 design routed to riv-ai-v2. Reflexivo was cut from that lane after an
ad-hoc n=5 smoke test found it giving direct advice, and the raw output of that
run was never saved — only the conclusion. This script makes the evidence
reproducible instead of remembered.

It reports, per lane:

  - **advice rate** — the fraction of turns whose prose contains an imperative
    or a suggested course of action. This is the defining constraint of the mode
    (`CLAUDE.md`: "hard no-advice constraint") and the reason Reflexivo stayed
    on the JSON lane.
  - **parse failure rate** — Reflexivo's prompt is JSON, not the marker protocol
    the prose lane uses elsewhere. An 8B holding nested JSON is a separate,
    harder question than whether it gives advice, so the two are reported
    separately and the raw model output is always dumped alongside.
  - **groundedness** — same metric as the /chat harness, over the
    doctrine_connection text.

The advice detector is an EVALUATION instrument, not a production filter. The
design is explicit that a half-working advice check in the request path is worse
than none; this one exists to be read by a human next to the text it flagged.

Usage:
    uv run python -m scripts.compare_reflect > logs/reflect-ab.md
"""

import argparse
import re
import unicodedata
from contextlib import ExitStack
from unittest.mock import patch

# Ordinary difficulty, deliberately below the crisis floor: `needs_crisis_note`
# short-circuits before any LLM call, so a crisis phrasing here would compare
# two identical fixed strings and measure nothing.
# `corpus_fit` records whether the two works Reflect is allowed to search
# (REFLECT_BOOKS: Espíritos + Evangelho) actually speak to the situation.
#
#   "bom"  — the Evangelho has chapters directly on this; a passage-fit test
#            must NOT make the model go quiet here, or the fix is a regression
#   "ruim" — retrieval returns vocabulary matches about other things. Grief is
#            the case that started this: for "perdi alguém que eu amava" the top
#            hit is LE 340, the agony of a Spirit about to reincarnate.
#
# Both groups exist for the same reason wrong_offer and wrong_silence do in
# compare_generators: an abstention rate on its own would reward a variant that
# refuses every situation, which would be useless.
SITUATIONS = [
    {
        "text": "estou passando por uma fase muito difícil no trabalho e me sinto sem valor",
        "corpus_fit": "bom",
    },
    {"text": "briguei com minha mãe e não sei como consertar", "corpus_fit": "bom"},
    {
        "text": "tenho muita inveja de uma amiga e isso me envergonha",
        "corpus_fit": "bom",
    },
    {"text": "não consigo perdoar quem me fez mal", "corpus_fit": "bom"},
    {
        "text": "perdi meu pai ano passado e ainda sinto uma saudade que não passa",
        "corpus_fit": "ruim",
    },
    {
        "text": "perdi alguém que eu amava e estou sofrendo muito com essa perda",
        "corpus_fit": "ruim",
    },
    {"text": "meu casamento acabou e eu me sinto um fracasso", "corpus_fit": "ruim"},
    {
        "text": "ando ansioso com o futuro e não consigo parar de me preocupar",
        "corpus_fit": "ruim",
    },
]


def _norm(text: str) -> str:
    """Lowercase, accent-stripped — the situations and the model output both mix
    accented and unaccented spellings."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


# Two shapes of advice, kept separate because they read differently when you
# inspect a flagged turn:
#
#   suggestion — names a course of action in the second person
#   imperative — a bare command verb opening a clause
#
# Both are matched on accent-stripped text. Word boundaries matter: "procure"
# must not fire inside "procurei", which is the reader narrating their own past.
_SUGGESTION = re.compile(
    r"\b(voce (pode|poderia|deve|deveria|precisa|precisaria)"
    r"|e importante que voce"
    r"|o (ideal|importante) e"
    r"|(sugiro|recomendo|aconselho)"
    r"|que tal"
    r"|seria bom (que voce|se voce)"
    r"|nao (se culpe|tenha medo|desista))\b"
)
_IMPERATIVE = re.compile(
    r"(^|[.!?;]\s+|\n)\s*"
    r"(tente|procure|busque|converse|fale|escreva|reserve|permita-se"
    r"|lembre-se|pense|respire|confie|aceite|perdoe|cuide|evite|comece)\b"
)


def advice_hits(text: str) -> list[str]:
    """Returns the matched advice fragments, so a flagged turn can be read
    rather than trusted."""
    if not text:
        return []
    normalized = _norm(text)
    hits = [m.group(0).strip() for m in _SUGGESTION.finditer(normalized)]
    hits += [m.group(2) for m in _IMPERATIVE.finditer(normalized)]
    return hits


# The model saying, in so many words, that the retrieved passages do not address
# the situation. Keyword-based and therefore a floor, not a ceiling: it will miss
# a paraphrase it has not seen. It is read alongside the answers themselves in
# the report, never on its own.
_ABSTAINS = re.compile(
    r"n[ãa]o\s+(?:tratam|falam|abordam|se\s+referem|trazem|dizem)\b"
    r"|n[ãa]o\s+h[áa]\s+(?:trechos?|passagens?)"
    r"|(?:trechos?|passagens?)[^.]{0,60}n[ãa]o\s+(?:tratam|falam|abordam)",
    re.IGNORECASE,
)


def abstains(text: str) -> bool:
    return bool(_ABSTAINS.search(text or ""))


def summarize_by_fit(rows: list[dict]) -> dict:
    """Abstention split by whether the corpus can serve the situation.

    The two numbers must move in opposite directions for the change to be a
    win: up on `ruim`, flat at zero on `bom`. A single overall rate would hide
    a variant that simply went quiet everywhere.
    """
    out = {}
    for fit in ("bom", "ruim"):
        group = [r for r in rows if r.get("corpus_fit") == fit]
        if not group:
            continue
        out[fit] = {
            "n": len(group),
            "abstention_rate": sum(
                1 for r in group if abstains(r["doctrine_connection"])
            )
            / len(group),
            "mean_groundedness": sum(r["groundedness"] for r in group) / len(group),
        }
    return out


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {}
    n = len(rows)
    return {
        "advice_rate": sum(1 for r in rows if r["advice_hits"]) / n,
        "advice_in_questions_rate": (
            sum(1 for r in rows if r["question_advice_hits"]) / n
        ),
        "parse_failure_rate": sum(1 for r in rows if r["generation_failed"]) / n,
        "mean_groundedness": sum(r["groundedness"] for r in rows) / n,
        "mean_questions": sum(len(r["reflection_questions"]) for r in rows) / n,
        "abstention_rate": sum(1 for r in rows if abstains(r["doctrine_connection"]))
        / n,
    }


# --- prompt variants ---------------------------------------------------------
#
# `_NO_ADVICE` is read from the module at call time inside
# `build_reflect_messages`, so a variant is one setattr. Keeping the historical
# texts here makes the A/B repeatable instead of a sequence of edits nobody can
# reproduce — the 2026-07-25 session compared three of them by editing the file
# between runs, which is exactly how you end up unable to tell a prompt effect
# from sampling noise.

_PERSONIFICATION_AND_SUICIDE = """\

Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que...", "o Espiritismo defende..."). \
Atribua as afirmações à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", \
"o texto indica que...", "Kardec escreve que...").

Nunca introduza temas de suicídio ou morte voluntária que a pessoa não mencionou. \
Se uma passagem recuperada tocar nesses temas sem relação direta com a situação \
relatada, simplesmente não a cite."""

_ADVICE_HEAD = """\
É absolutamente proibido fazer sugestões de ação. Nunca diga "você deveria", \
"recomendo", "tente", "considere", ou equivalentes. Não sugira medicação, \
doação, separação, mudança de comportamento, ou qualquer outro curso de ação. \
Sua única função é mostrar o que a doutrina diz e oferecer perguntas para \
reflexão pessoal. Nunca elabore doutrina além dos trechos recuperados."""

_INTIMACY = """\

Mantenha as perguntas no plano do que o texto propõe. Não peça à pessoa que \
detalhe sua intimidade nem investigue sentimentos que ela não trouxe."""

# baseline — the advice ban stated only in the declarative register.
_V_BASELINE = _ADVICE_HEAD + _PERSONIFICATION_AND_SUICIDE

# v1 — adds the interrogative form, enumerating banned openers.
_V_STEMS = (
    _ADVICE_HEAD
    + """

Uma pergunta de reflexão convida a pessoa a OLHAR, nunca a PLANEJAR. Ela abre um \
ângulo que a passagem ilumina na situação — não um passo a ser dado. Nunca \
escreva uma pergunta que pressuponha um curso de ação. Uma pergunta como "De que \
maneira você pode…", "Como você poderia…" ou "O que você pode fazer para…" é \
conselho com ponto de interrogação: não pergunta SE aquele caminho é o certo, \
apenas COMO segui-lo. Isso vale mesmo quando o caminho pressuposto parece \
evidentemente bom — perdoar, reconstruir, crescer, aceitar, encontrar equilíbrio."""
    + _INTIMACY
    + _PERSONIFICATION_AND_SUICIDE
)

VARIANTS = {"baseline": _V_BASELINE, "stems": _V_STEMS}


# --- passage-fit variants (MEASURED AND REJECTED, 2026-07-26) ----------------
#
# Kept so the result stays reproducible, and so nobody proposes it a second
# time. Re-running needs the {passage_fit} slot back in _SYSTEM_TEMPLATE; the
# patch below uses create=True for the constant.
#
# The idea: retrieval ranks by embedding proximity, which tracks vocabulary and
# therefore affect — for "perdi alguém que eu amava" the top hit is LE 340, the
# agony of a Spirit about to reincarnate, while the apt passage (a prayer for
# the departed) came third. The prompt had never given the model permission to
# discard a retrieved passage, so it built on the first two and wrote the seam
# in plain sight.
#
# Why it failed (8 situations, temperature 0):
#   - abstained 1/4 on `bom` and 1/4 on `ruim` — the same rate, when the whole
#     point was for those to move in opposite directions
#   - the one abstention landed on work/self-worth, which the Evangelho covers
#     directly, and on NEITHER grief case, which is what started this
#   - "abstaining" did not stop it: "as passagens não tratam diretamente ...
#     mas podemos refletir sobre" — it learned to announce the seam rather than
#     stop sewing, using the exact connective the rule banned
#   - advice_in_questions_rate doubled, 0.25 -> 0.50
#
# The conclusion is about capability, not wording: the model cannot judge
# aptness better than the ranking can. Permission to discard produces arbitrary
# hedging, not discernment. This is a retrieval problem and has to be fixed in
# retrieval.
_F_SEM_TESTE = ""

# "com-teste" must stay a byte-for-byte copy of reflect_prompt._PASSAGE_FIT, or
# the run stops describing what the file does. Asserted below.
_F_COM_TESTE = """\
A ordem das passagens não indica qualidade, e nem toda passagem recuperada serve \
à situação: a busca aproxima vocabulário, de modo que um trecho pode repetir as \
mesmas palavras de sofrimento e tratar de outra coisa.

Antes de usar cada passagem, aplique este teste: ela fala do que a pessoa \
trouxe, ou apenas se parece com o que ela escreveu? Use somente as que falam — \
ainda que sobrem poucas, ainda que a melhor não seja a primeira da lista.

Se você precisar de uma frase de ligação para a passagem caber na situação, ela \
não cabe. Descarte-a.

Se nenhuma passar no teste, não construa a ponte. Diga em "doctrine_connection", \
com franqueza e sem constrangimento, que os trechos recuperados não tratam \
diretamente do que a pessoa vive; acolha assim mesmo e ofereça perguntas que \
nasçam da situação dela."""

PASSAGE_FIT_VARIANTS = {"sem-teste": _F_SEM_TESTE, "com-teste": _F_COM_TESTE}


def _resolve_variant(name: str) -> str | None:
    """`atual` means "whatever is in reflect_prompt.py right now" — no patch."""
    return None if name == "atual" else VARIANTS[name]


def _prose_shim(raw_sink: list[str]):
    """Replacement for `create_json_completion` inside reflect.py that routes the
    Reflexivo call to the prose lane.

    Production code pins Reflexivo to the JSON lane on purpose, so there is no
    setting that redirects it — this monkeypatch is how the comparison happens
    without loosening that in `src/`. Mirrors the prose lane's own call shape
    (`src/rag/prose.py`): temperature=0, and no `response_format`, which the
    local llama.cpp/Ollama surface does not honor the way a hosted API does.
    """
    from src.core.config import settings
    from src.rag.llm_client import get_client

    def shim(client, model, messages, max_tokens, structured=None):
        response = get_client("prose").chat.completions.create(
            model=settings.resolved_prose_model,
            max_tokens=max_tokens,
            messages=messages,
            temperature=0,
        )
        raw_sink.append(response.choices[0].message.content or "")
        return response

    return shim


def _json_shim(temperature: float):
    """Production's Reflexivo call, with `temperature` pinned.

    `reflect.py` does not pass a temperature, so the JSON lane samples. That is
    right for production — a study companion that answers identically forever is
    worse — but it makes prompt A/B unreadable: on 2026-07-25 the same situation
    produced the best question of any run and the worst, across two prompts,
    and neither difference could be attributed. Pinning 0 here makes a prompt
    change the only thing that moved.

    This measures the prompt's central tendency, NOT its behaviour under
    production sampling. A variant that wins at 0 can still misbehave when
    sampled; that needs its own repeated-sampling run.
    """
    from src.rag.llm_client import create_json_completion

    def shim(client, model, messages, max_tokens, structured=None):
        return (
            create_json_completion(client, model, messages, max_tokens, structured)
            if temperature is None
            else client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                temperature=temperature,
            )
        )

    return shim


def _run_lane(
    prose_provider: str | None,
    temperature: float | None = 0.0,
    variant: str | None = None,
    passage_fit: str | None = None,
) -> list[dict]:
    """Runs every situation with Reflexivo pointed at `prose_provider`.

    `prose_provider=None` means the JSON lane. `variant` replaces
    `reflect_prompt._NO_ADVICE` for the duration of the run (None = the file as
    it stands). `temperature=None` restores production sampling.
    """
    from src.core.config import settings
    from src.rag import llm_client
    from src.rag.groundedness import groundedness_score
    from src.rag.reflect import reflect

    settings.prose_provider = prose_provider
    llm_client._clients.clear()

    rows = []
    for case in SITUATIONS:
        situation = case["text"]
        raw_sink: list[str] = []
        shim = (
            _prose_shim(raw_sink)
            if prose_provider is not None
            else _json_shim(temperature)
        )
        with ExitStack() as stack:
            stack.enter_context(patch("src.rag.reflect.create_json_completion", shim))
            if variant is not None:
                stack.enter_context(patch("src.rag.reflect_prompt._NO_ADVICE", variant))
            if passage_fit is not None:
                # reflect_prompt has no _PASSAGE_FIT slot any more (the rule was
                # measured and rejected on 2026-07-26 — see the note above
                # PASSAGE_FIT_VARIANTS). `create=True` re-creates the attribute
                # for the duration of a re-run, so the rejected variant stays
                # reproducible without living in production.
                stack.enter_context(
                    patch(
                        "src.rag.reflect_prompt._PASSAGE_FIT",
                        passage_fit,
                        create=True,
                    )
                )
            result = reflect(situation)

        # `sources` carries the excerpt text under a different key than the
        # retriever's chunks; groundedness_score reads `content`.
        chunks = [{"content": s["excerpt"]} for s in result["sources"]]
        prose = f"{result['opening']}\n{result['doctrine_connection']}".strip()
        rows.append(
            {
                "situation": situation,
                "corpus_fit": case["corpus_fit"],
                "opening": result["opening"],
                "doctrine_connection": result["doctrine_connection"],
                "reflection_questions": result["reflection_questions"],
                "is_closing": result["is_closing"],
                "generation_failed": result["generation_failed"],
                "safety_level": result["safety_level"],
                "groundedness": groundedness_score(prose, chunks) if chunks else 0.0,
                "advice_hits": advice_hits(prose),
                "question_advice_hits": advice_hits(
                    " ".join(result["reflection_questions"])
                ),
                "raw": raw_sink[0] if raw_sink else "",
            }
        )
    return rows


def _format_lane(row: dict, label: str) -> list[str]:
    lines = [
        f"**{label}**",
        "",
        f"- opening: {row['opening'] or '_(vazio)_'}",
        f"- doctrine_connection: {row['doctrine_connection'] or '_(vazio)_'}",
        f"- perguntas: {row['reflection_questions']}",
        f"- is_closing: {row['is_closing']} · generation_failed: "
        f"{row['generation_failed']} · safety_level: {row['safety_level']}",
        f"- groundedness: {row['groundedness']:.3f}",
        f"- ⚠️ conselho na prosa: {row['advice_hits'] or 'nenhum'}",
        f"- ⚠️ conselho nas perguntas: {row['question_advice_hits'] or 'nenhum'}",
    ]
    if row["raw"]:
        lines += ["", "<details><summary>saída bruta do modelo</summary>", ""]
        lines += ["```", row["raw"], "```", "</details>"]
    lines.append("")
    return lines


def format_report(pairs: list[dict]) -> str:
    lines = ["# /reflect — RIV AI v2 vs current provider", ""]
    for p in pairs:
        lines += [f"## {p['situation']}", ""]
        lines += _format_lane(p["prose"], "prose lane (riv-ai-v2)")
        lines += _format_lane(p["json"], "json lane (current)")
        lines += ["---", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prose-provider",
        default="ollama",
        help="provider to route Reflexivo through (default: ollama)",
    )
    parser.add_argument(
        "--lane",
        choices=["prose", "json", "both"],
        default="both",
        help="which lane to run. `json` alone is the right choice when iterating "
        "on the Reflexivo prompt: the prose lane costs hours on local CPU and "
        "its answer is already known (6/6 JSON parse failures on 2026-07-25)",
    )
    parser.add_argument(
        "--variants",
        default="",
        help="comma-separated prompt variants to compare on the JSON lane "
        f"({', '.join(['atual', *VARIANTS])}). Empty = whatever is in the file.",
    )
    parser.add_argument(
        "--passage-fit",
        default="",
        help="comma-separated passage-fit variants to compare on the JSON lane "
        f"({', '.join(PASSAGE_FIT_VARIANTS)}). Empty = whatever is in the file.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="pinned for A/B so a prompt change is the only thing that moved "
        "(default: 0.0). Pass -1 to restore production sampling.",
    )
    args = parser.parse_args()
    temperature = None if args.temperature < 0 else args.temperature

    if args.passage_fit:
        names = [n.strip() for n in args.passage_fit.split(",") if n.strip()]
        print(
            f"# /reflect — teste de aptidão da passagem @ temperature={temperature}\n"
        )
        results = {}
        for name in names:
            rows = _run_lane(None, temperature, None, PASSAGE_FIT_VARIANTS[name])
            results[name] = rows
            print(f"## variante: {name}\n")
            for r in rows:
                print(f"### [{r['corpus_fit']}] {r['situation']}\n")
                print("\n".join(_format_lane(r, name)))
            print("---\n")
        print("## Summary\n")
        for name, rows in results.items():
            print(f"- {name}: {summarize(rows)}")
            print(f"  por aptidão do acervo: {summarize_by_fit(rows)}")
        return

    if args.variants:
        names = [n.strip() for n in args.variants.split(",") if n.strip()]
        print(f"# /reflect — prompt variants @ temperature={temperature}\n")
        results = {}
        for name in names:
            rows = _run_lane(None, temperature, _resolve_variant(name))
            results[name] = rows
            print(f"## variante: {name}\n")
            for r in rows:
                print(f"### {r['situation']}\n")
                print("\n".join(_format_lane(r, name)))
            print("---\n")
        print("## Summary\n")
        for name, rows in results.items():
            print(f"- {name}: {summarize(rows)}")
        return

    prose_rows = (
        _run_lane(args.prose_provider, temperature)
        if args.lane in ("prose", "both")
        else []
    )
    json_rows = _run_lane(None, temperature) if args.lane in ("json", "both") else []

    if prose_rows and json_rows:
        pairs = [
            {"situation": p["situation"], "prose": p, "json": j}
            for p, j in zip(prose_rows, json_rows)
        ]
        print(format_report(pairs))
    else:
        # Single lane: still print every turn in full. The advice question is
        # editorial — the number is only there to catch regressions.
        rows = prose_rows or json_rows
        label = "prose lane (riv-ai-v2)" if prose_rows else "json lane (current)"
        lines = [f"# /reflect — {label}", ""]
        for r in rows:
            lines += [f"## {r['situation']}", ""] + _format_lane(r, label) + ["---", ""]
        print("\n".join(lines))

    print("## Summary\n")
    if prose_rows:
        print(f"- prose lane (riv-ai-v2): {summarize(prose_rows)}")
    if json_rows:
        print(f"- json lane (current):    {summarize(json_rows)}")
    print()
    print(
        "_advice_rate is an evaluation instrument, not a production filter — "
        "read the flagged text before trusting the number._"
    )


if __name__ == "__main__":
    main()
