"""A/B two versions of the /chat prompt on one model.

This script used to compare two *providers* — a local prose lane (riv-ai-v2)
against the 70B baseline. That question is settled and the prose lane is gone
from here: everything below runs on whatever `LLM_PROVIDER` resolves to, and a
"lane" now means **a prompt variant**, not a model. Comparing two prompts across
two models could never attribute a difference to either one.

What it reports, per variant:

  - mean groundedness — how close answers stay to their retrieved passages
  - hallucinated-citation rate — how often the model cites outside that set
  - the [SEGUIR] numbers — whether follow-up chips were offered, how many, and
    whether they were offered on the turns where a chip actually belongs
  - style metrics — length, inline-reference density, paragraph count

Read as a *comparison between variants*, never as absolute thresholds.

Each variant is run and persisted independently (`logs/lane-<name>.json`),
written after every single case rather than at the end. The 2026-07-25 run lost
fifteen answers to a mid-run provider quota error because nothing was written
until the last one finished. Now a run that dies keeps everything it produced.

Sampling is pinned to temperature 0 by default. That is wrong for production —
a study companion that answers identically forever is worse — but it makes a
prompt A/B readable: it leaves the prompt as the only thing that moved. A
variant that wins at 0 can still misbehave when sampled; that needs its own
repeated-sampling run.

Usage:
    uv run python -m scripts.compare_generators --variants atual,seguir-opcional
    uv run python -m scripts.compare_generators --report-only > logs/ab.md
"""

import argparse
import json
import os
import re
from unittest.mock import patch

# A conversation is not a list of questions. These cases are the *paths* a
# reader actually takes through Dialogar, because the thing under test —
# whether a follow-up chip belongs on this turn — depends entirely on which
# path the turn sits in, and a flat list of doctrinal openers can only ever
# measure the one path where chips were never in doubt.
#
# `history` is the /chat history shape ({role, content}), so the multi-turn
# cases are the real thing rather than a first turn wearing a label.
#
# `expects_seguir`:
#   True  — an open topic the passages can still extend; a chip earns its place
#   False — the turn closed, went personal, or fell outside the works; a chip
#           here reads as a funnel, not as help
#   None  — legitimately either way; counted in the rates, excluded from the
#           agreement score so a judgement call cannot inflate it
CASES = [
    # ── the path chips were designed for ────────────────────────────────────
    {
        "id": "abertura-espirito",
        "path": "abertura",
        "question": "o que é o espírito?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-morte",
        "path": "abertura",
        "question": "o que acontece depois da morte?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-reencarnacao",
        "path": "abertura",
        "question": "o que é a reencarnação e por que ela existe?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-causa-efeito",
        "path": "abertura",
        "question": "o que é a lei de causa e efeito?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-prece",
        "path": "abertura",
        "question": "o que é a prece segundo a doutrina?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-sofrimento",
        "path": "abertura",
        "question": "por que existe o sofrimento?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-caridade",
        "path": "abertura",
        "question": "o que Kardec diz sobre a caridade?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-livre-arbitrio",
        "path": "abertura",
        "question": "o que é o livre-arbítrio?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-alma-espirito",
        "path": "abertura",
        "question": "qual a diferença entre alma e espírito?",
        "history": [],
        "expects_seguir": True,
    },
    {
        "id": "abertura-provacoes",
        "path": "abertura",
        "question": "o que são as provações?",
        "history": [],
        "expects_seguir": True,
    },
    # ── digging into an answer just given ───────────────────────────────────
    {
        "id": "aprofunda-nao-entendi",
        "path": "aprofundamento",
        "question": "como assim? me explica mais que não entendi",
        "history": [
            {"role": "user", "content": "como é a comunicação dos espíritos?"},
            {
                "role": "assistant",
                "content": (
                    "Kardec escreve que a comunicação entre os Espíritos e os "
                    "homens se faz por meio do perispírito, envoltório fluídico "
                    "que faz parte integrante do Espírito."
                ),
            },
        ],
        "expects_seguir": True,
    },
    {
        "id": "aprofunda-confirmacao",
        "path": "aprofundamento",
        "question": "então os espíritos ensinaram o espiritismo? como isso é possível?",
        "history": [
            {"role": "user", "content": "qual a relação entre o espiritismo e Cristo?"},
            {
                "role": "assistant",
                "content": (
                    "A passagem mostra que o Espiritismo é fruto do ensino "
                    "coletivo dos Espíritos, presidido pelo Espírito de Verdade."
                ),
            },
        ],
        "expects_seguir": True,
    },
    # ── the reader is done ──────────────────────────────────────────────────
    {
        "id": "encerra-entendi",
        "path": "encerramento",
        "question": "entendi, era isso mesmo que eu queria saber",
        "history": [
            {"role": "user", "content": "o que é o perispírito?"},
            {
                "role": "assistant",
                "content": (
                    "Kardec escreve que o perispírito é o envoltório fluídico "
                    "que serve de laço entre o Espírito e a matéria."
                ),
            },
        ],
        "expects_seguir": False,
    },
    {
        "id": "encerra-ja-respondida",
        "path": "encerramento",
        "question": "e o perispírito, o que é mesmo?",
        "history": [
            {"role": "user", "content": "o que é o perispírito?"},
            {
                "role": "assistant",
                "content": (
                    "Kardec escreve que o perispírito é o envoltório fluídico "
                    "que serve de laço entre o Espírito e a matéria, e é o "
                    "agente das comunicações mediúnicas."
                ),
            },
        ],
        "expects_seguir": False,
    },
    # ── the turn stops being about doctrine and becomes about a person ──────
    {
        "id": "pessoal-mae-taro",
        "path": "pessoal",
        "question": "minha mãe joga tarô, ela é uma médium ruim ou mexe com coisa do mal?",
        "history": [
            {"role": "user", "content": "existem médiuns ruins?"},
            {
                "role": "assistant",
                "content": (
                    "Kardec escreve que há médiuns que recebem comunicações de "
                    "Espíritos imperfeitos."
                ),
            },
        ],
        "expects_seguir": False,
    },
    {
        "id": "pessoal-briga-irmao",
        "path": "pessoal",
        "question": "briguei feio com meu irmão e não sei mais como olhar pra ele",
        "history": [],
        "expects_seguir": False,
    },
    {
        "id": "pessoal-medo-morrer",
        "path": "pessoal",
        "question": "tenho muito medo de morrer, penso nisso todo dia",
        "history": [],
        "expects_seguir": False,
    },
    # ── outside the five works ──────────────────────────────────────────────
    {
        "id": "fora-escopo-biblia",
        "path": "fora-de-escopo",
        "question": "o que o Antigo Testamento diz sobre os anjos?",
        "history": [],
        "expects_seguir": False,
    },
    {
        "id": "fora-escopo-biografia",
        "path": "fora-de-escopo",
        "question": "em que ano Allan Kardec morreu e onde ele está enterrado?",
        "history": [],
        "expects_seguir": False,
    },
    {
        "id": "fora-escopo-chico",
        "path": "fora-de-escopo",
        "question": "o que Chico Xavier escreveu sobre o umbral?",
        "history": [],
        "expects_seguir": False,
    },
    # ── sensitive as a topic, not as ideation: must answer AND carry CVV ────
    {
        "id": "sensivel-suicidio-topico",
        "path": "topico-sensivel",
        "question": "o que a doutrina espírita diz sobre o suicídio?",
        "history": [],
        "expects_seguir": False,
    },
    {
        "id": "sensivel-luto",
        "path": "topico-sensivel",
        "question": "meu pai morreu mês passado, onde ele está agora?",
        "history": [],
        "expects_seguir": False,
    },
    # ── asking for a course of action ───────────────────────────────────────
    {
        "id": "pratica-devo-procurar",
        "path": "pratica",
        "question": "devo procurar um centro espírita pra desenvolver mediunidade?",
        "history": [],
        "expects_seguir": None,
    },
    {
        "id": "pratica-como-orar",
        "path": "pratica",
        "question": "como devo orar segundo Kardec?",
        "history": [],
        "expects_seguir": None,
    },
    # ── a specific numbered entry ───────────────────────────────────────────
    {
        "id": "referencia-questao",
        "path": "referencia-item",
        "question": "explique a questão 132 do Livro dos Espíritos",
        "history": [],
        "expects_seguir": None,
    },
    # ── comparison with something the works do not cover ────────────────────
    {
        "id": "comparativo-religioes",
        "path": "comparativo",
        "question": "qual a diferença entre a reencarnação espírita e o carma do budismo?",
        "history": [],
        "expects_seguir": None,
    },
]


# --- prompt variants ---------------------------------------------------------
#
# `_SEGUIR_RULE` is read from the module inside `build_messages`, so a variant
# is one patch. Keeping both texts here makes the A/B repeatable instead of a
# sequence of file edits nobody can reproduce.

# atual — two questions, unconditionally. What production does today.
_V_ATUAL = """\
2. [SEGUIR: pergunta 1 | pergunta 2] com DUAS perguntas curtas de continuação \
que o usuário poderia fazer em seguida, separadas por "|". Cada pergunta deve \
ser respondível pelas obras de Kardec e, de preferência, ligada aos temas das \
passagens recuperadas — nunca sugira algo que as obras não abordam. Nunca sugira \
uma pergunta que já foi feita ou já foi respondida nesta conversa, nem uma \
reformulação equivalente dela — proponha ângulos genuinamente novos."""

# seguir-opcional — the chips become the model's call, stated as a TEST rather
# than as "ofereça se achar útil". The _NO_ADVICE history in reflect_prompt.py
# is the evidence for that choice: a soft instruction is complied with
# unevenly, and enumerating surface forms gets routed around one synonym away.
# Naming the condition leaves nothing to route around.
_V_SEGUIR_OPCIONAL = """\
2. [SEGUIR: pergunta 1 | pergunta 2] com ATÉ duas perguntas curtas de \
continuação, separadas por "|", ou [SEGUIR:] vazio quando nenhuma se justificar. \
Oferecer perguntas não é obrigatório e o vazio não é falha.

Antes de escrever esta linha, aplique este teste: existe um ângulo que as \
passagens recuperadas sustentam e que esta resposta ainda não cobriu? Se não \
existir, escreva [SEGUIR:] vazio. Uma pergunta oferecida sem esse ângulo empurra \
a conversa para frente em vez de responder à que foi feita.

Escreva [SEGUIR:] vazio também quando a mensagem não for um pedido de estudo: \
quando a pessoa encerra o assunto, quando fala de si mesma ou de alguém próximo \
em vez de perguntar sobre a doutrina, ou quando as passagens não continham o que \
ela pediu. Nesses turnos, quem decide o que vem depois é ela, não você.

Quando houver ângulo, cada pergunta deve ser respondível pelas obras de Kardec e \
ligada aos temas das passagens recuperadas — nunca sugira algo que as obras não \
abordam. Nunca sugira uma pergunta que já foi feita ou já foi respondida nesta \
conversa, nem uma reformulação equivalente dela."""

VARIANTS = {"atual": _V_ATUAL, "seguir-opcional": _V_SEGUIR_OPCIONAL}


def _resolve_variant(name: str) -> str | None:
    """`arquivo` means "whatever is in prompt.py right now" — no patch."""
    if name == "arquivo":
        return None
    return VARIANTS[name]


# An inline reference the reader sees in the prose — "item 659", "questão 872",
# a work's name in quotes. Distinct from the [FONTES:] trailer, which is machine
# -readable and stripped before display.
_INLINE_REF = re.compile(r"item\s+\d+|quest[ãa]o\s+\d+|\"O\s+[A-ZÀ-Ý]", re.IGNORECASE)


def style_metrics(rows: list[dict]) -> dict:
    """Length and inline-reference density.

    Unlike every judgment-based metric in these harnesses, these are
    deterministic properties of the text: they do not depend on a model's
    opinion and do not move between runs. That makes them the only numbers here
    that can settle a small prompt change on their own.
    """
    if not rows:
        return {"mean_chars": 0.0, "mean_inline_refs": 0.0, "mean_paragraphs": 0.0}
    n = len(rows)
    return {
        "mean_chars": sum(len(r["answer"]) for r in rows) / n,
        "mean_inline_refs": sum(len(_INLINE_REF.findall(r["answer"])) for r in rows)
        / n,
        "mean_paragraphs": sum(r["answer"].count("\n\n") + 1 for r in rows) / n,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"mean_groundedness": 0.0, "hallucinated_citation_rate": 0.0}
    n = len(rows)
    return {
        "mean_groundedness": sum(r["groundedness"] for r in rows) / n,
        "hallucinated_citation_rate": sum(1 for r in rows if not r["confiavel"]) / n,
    }


def seguir_metrics(rows: list[dict]) -> dict:
    """The numbers this A/B exists for.

    `agreement` is the one that matters, and it is deliberately not the same as
    `offer_rate`: a variant that never offers a chip scores a perfect silence
    rate and is useless. Agreement asks whether the chips landed on the turns
    where a chip belongs, scored only over cases with a stated expectation —
    the `expects_seguir: None` cases are counted in the rates and excluded here,
    so a judgement call cannot pad the score.
    """
    if not rows:
        return {
            "offer_rate": 0.0,
            "mean_count": 0.0,
            "agreement": None,
            "wrong_silence": 0,
            "wrong_offer": 0,
        }
    n = len(rows)
    judged = [r for r in rows if r["expects_seguir"] is not None]
    # Offered a chip where the turn had closed / gone personal / fallen out of
    # scope. This is the failure the reader actually complained about.
    wrong_offer = [r for r in judged if r["expects_seguir"] is False and r["n_seguir"]]
    # Stayed silent on an open doctrinal topic — the regression risk of the
    # change, and the reason offer_rate alone cannot decide anything.
    wrong_silence = [
        r for r in judged if r["expects_seguir"] is True and not r["n_seguir"]
    ]
    agreed = len(judged) - len(wrong_offer) - len(wrong_silence)
    return {
        "offer_rate": sum(1 for r in rows if r["n_seguir"]) / n,
        "mean_count": sum(r["n_seguir"] for r in rows) / n,
        "agreement": (agreed / len(judged)) if judged else None,
        "wrong_silence": len(wrong_silence),
        "wrong_offer": len(wrong_offer),
    }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = pct * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def similarity_distribution(all_sims: list[float]) -> dict:
    """Distribution of per-chunk answer-to-chunk cosines across every case on a
    variant — the data `source_min_similarity` should be picked from, per the
    comment in src/core/config.py.

    Kept when the prose lane was removed: it calibrates a retrieval threshold
    and never had anything to do with which provider wrote the prose.
    """
    if not all_sims:
        return {
            "min": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "max": 0.0,
            "kept_at_0.3": 0,
            "kept_at_0.4": 0,
            "kept_at_0.5": 0,
            "kept_at_0.6": 0,
        }
    s = sorted(all_sims)
    return {
        "min": s[0],
        "median": _percentile(s, 0.5),
        "p25": _percentile(s, 0.25),
        "p75": _percentile(s, 0.75),
        "max": s[-1],
        "kept_at_0.3": sum(1 for v in all_sims if v >= 0.3),
        "kept_at_0.4": sum(1 for v in all_sims if v >= 0.4),
        "kept_at_0.5": sum(1 for v in all_sims if v >= 0.5),
        "kept_at_0.6": sum(1 for v in all_sims if v >= 0.6),
    }


def seguir_by_path(rows: list[dict]) -> dict:
    """Offer rate per user path. The aggregate can hide the whole finding: a
    variant can hold its overall rate steady while moving every chip off the
    personal turns and onto the doctrinal ones, which is exactly the win."""
    paths: dict[str, list[dict]] = {}
    for r in rows:
        paths.setdefault(r["path"], []).append(r)
    return {
        p: {
            "n": len(rs),
            "offer_rate": sum(1 for r in rs if r["n_seguir"]) / len(rs),
            "expects": rs[0]["expects_seguir"],
        }
        for p, rs in sorted(paths.items())
    }


def _pinned_prose_completion(temperature: float):
    """Stands in for `generator.prose_completion`, pinning sampling.

    The production function leaves temperature to the provider default while
    the prose lane is off (`prose.py:32`), deliberately, so that turning the
    lane off changes nothing. That is right for production and useless for an
    A/B, where an unpinned temperature makes a prompt difference and sampling
    noise indistinguishable.

    Safe to build the call by hand here only because `_run_variant` forces
    `settings.prose_provider = None` first: with the lane off,
    `resolved_prose_model` is `resolved_chat_model` and `get_client("prose")`
    is the main client, so this is the same single 70B everything else uses.
    """
    from src.core.config import settings
    from src.rag.llm_client import get_client

    def shim(system: str, messages: list[dict], max_tokens: int = 1024):
        payload = [{"role": "system", "content": system}] + messages
        response = get_client("prose").chat.completions.create(
            model=settings.resolved_prose_model,
            max_tokens=max_tokens,
            messages=payload,
            temperature=temperature,
        )
        return response.choices[0].message.content

    return shim


LANE_DIR = "logs"


def lane_path(lane: str) -> str:
    return os.path.join(LANE_DIR, f"lane-{lane}.json")


def save_lane(lane: str, chat: list[dict], sims: list[float] | None = None) -> None:
    """Persist a variant's results so far.

    Called after every case, not once at the end — a provider quota error
    mid-run must cost the remaining cases, never the finished ones. Written to a
    temp file and renamed so a crash mid-write cannot leave a truncated file
    that later reads as valid-but-short.
    """
    os.makedirs(LANE_DIR, exist_ok=True)
    tmp = lane_path(lane) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(
            {"lane": lane, "chat": chat, "similarities": sims or []},
            fh,
            ensure_ascii=False,
            indent=2,
        )
    os.replace(tmp, lane_path(lane))


def load_lane(lane: str) -> dict | None:
    """Reads a persisted variant, or None when it has not been run yet."""
    try:
        with open(lane_path(lane), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def _run_variant(
    name: str, variant: str | None, temperature: float | None = 0.0
) -> list[dict]:
    """Runs every case with `prompt._SEGUIR_RULE` replaced by `variant`."""
    from src.core.config import settings
    from src.rag import generator, llm_client
    from src.rag.citations import (
        extract_model_citations,
        retrieved_ids,
        validate_model_citations,
    )
    from src.rag.groundedness import groundedness_score, per_chunk_similarities
    from src.rag.retriever import retrieve

    # One model, always. A prompt A/B run across two providers could never
    # attribute a difference to either one, so the prose lane is forced off here
    # even if the environment turns it on.
    settings.prose_provider = None
    llm_client._clients.clear()

    rows: list[dict] = []
    all_sims: list[float] = []
    for case in CASES:
        with _variant_patches(variant, temperature):
            result = generator.generate(case["question"], case["history"])
        chunks = retrieve(case["question"])
        report = validate_model_citations(
            extract_model_citations(result["answer"]), retrieved_ids(chunks)
        )
        seguir = result.get("suggested_questions") or []
        rows.append(
            {
                "id": case["id"],
                "path": case["path"],
                "question": case["question"],
                "expects_seguir": case["expects_seguir"],
                "answer": result["answer"],
                "seguir": seguir,
                "n_seguir": len(seguir),
                "safety_level": result.get("safety_level"),
                "not_found": result.get("not_found"),
                "groundedness": groundedness_score(result["answer"], chunks),
                "confiavel": report["confiavel"],
            }
        )
        all_sims.extend(per_chunk_similarities(result["answer"], chunks))
        save_lane(name, rows, all_sims)
    return rows


def _variant_patches(variant: str | None, temperature: float | None):
    from contextlib import ExitStack

    stack = ExitStack()
    if variant is not None:
        stack.enter_context(patch("src.rag.prompt._SEGUIR_RULE", variant))
    if temperature is not None:
        stack.enter_context(
            patch(
                "src.rag.generator.prose_completion",
                _pinned_prose_completion(temperature),
            )
        )
    return stack


def format_report(
    lanes: dict[str, list[dict]], sims: dict[str, list[float]] | None = None
) -> str:
    lines = ["# /chat — variantes da regra [SEGUIR]", ""]
    names = list(lanes)

    lines += ["## Por caso", ""]
    by_id: dict[str, dict] = {}
    for name, rows in lanes.items():
        for r in rows:
            by_id.setdefault(r["id"], {})[name] = r
    for case in CASES:
        rows = by_id.get(case["id"])
        if not rows:
            continue
        expects = {True: "sim", False: "não", None: "—"}[case["expects_seguir"]]
        lines += [
            f"### [{case['path']}] {case['question']}",
            "",
            f"_chip esperado: **{expects}**_",
            "",
        ]
        for name in names:
            r = rows.get(name)
            if not r:
                continue
            chips = " | ".join(r["seguir"]) if r["seguir"] else "_(nenhum)_"
            lines += [
                f"**{name}** — {r['n_seguir']} chip(s): {chips}",
                "",
                f"> {r['answer'][:400]}{'…' if len(r['answer']) > 400 else ''}",
                "",
                f"_groundedness {r['groundedness']:.3f} · citações confiáveis: "
                f"{r['confiavel']}_",
                "",
            ]
        lines += ["---", ""]

    lines += ["## Resumo", ""]
    for name, rows in lanes.items():
        lines += [
            f"### {name} ({len(rows)} casos)",
            "",
            f"- qualidade: {summarize(rows)}",
            f"- estilo:    {style_metrics(rows)}",
            f"- SEGUIR:    {seguir_metrics(rows)}",
            "",
            "| caminho | n | chip esperado | taxa de oferta |",
            "|---|---|---|---|",
        ]
        for path, m in seguir_by_path(rows).items():
            expects = {True: "sim", False: "não", None: "—"}[m["expects"]]
            lines.append(f"| {path} | {m['n']} | {expects} | {m['offer_rate']:.2f} |")
        lines.append("")
    if sims and any(sims.values()):
        lines += [
            "## Distribuição do cosseno resposta-trecho "
            "(calibração de source_min_similarity)",
            "",
        ]
        for name, vals in sims.items():
            if vals:
                lines.append(f"- {name}: {similarity_distribution(vals)}")
        lines.append("")

    if len(lanes) < 2:
        lines.append(
            "> ⚠️ Só uma variante tem dados. Estes números são uma comparação "
            "ou não são nada — rode a outra antes de concluir."
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variants",
        default="",
        help="comma-separated prompt variants to run "
        f"({', '.join(['arquivo', *VARIANTS])}). Empty = run nothing, report "
        "from whatever lane files exist.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="sampling temperature; pass -1 to restore production sampling",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="run nothing; rebuild the report from the persisted lane files",
    )
    args = parser.parse_args()

    temperature = None if args.temperature < 0 else args.temperature
    names = [n.strip() for n in args.variants.split(",") if n.strip()]

    if not args.report_only:
        for name in names:
            _run_variant(name, _resolve_variant(name), temperature)

    report_names = names or list(VARIANTS)
    lanes = {}
    sims = {}
    for name in report_names:
        lane = load_lane(name)
        if lane:
            lanes[name] = lane["chat"]
            # .get: lane files written before similarities were collected are
            # still valid input, they simply contribute no distribution.
            sims[name] = lane.get("similarities", [])
    print(format_report(lanes, sims))


if __name__ == "__main__":
    main()
