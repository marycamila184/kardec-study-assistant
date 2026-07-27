import sys
from unittest.mock import patch

import pytest

import scripts.compare_generators as cg
from scripts.compare_generators import (
    VARIANTS,
    _sanitize_lane_name,
    format_report,
    lane_path,
    main,
    seguir_by_path,
    seguir_metrics,
    similarity_distribution,
    summarize,
)


def _row(
    case_id="c",
    path="abertura",
    n_seguir=2,
    expects=True,
    groundedness=0.8,
    confiavel=True,
    finish_reason="stop",
):
    return {
        "id": case_id,
        "path": path,
        "question": f"pergunta {case_id}",
        "expects_seguir": expects,
        "answer": f"resposta {case_id}",
        "seguir": ["q1", "q2"][:n_seguir],
        "n_seguir": n_seguir,
        "groundedness": groundedness,
        "confiavel": confiavel,
        "finish_reason": finish_reason,
    }


def test_summarize_averages_metrics():
    rows = [_row("a", groundedness=0.8), _row("b", groundedness=0.6, confiavel=False)]
    out = summarize(rows)
    assert out["mean_groundedness"] == 0.7
    assert out["hallucinated_citation_rate"] == 0.5


def test_summarize_handles_empty_rows():
    out = summarize([])
    assert out["mean_groundedness"] == 0.0
    assert out["hallucinated_citation_rate"] == 0.0


# --- [SEGUIR] metrics --------------------------------------------------------


def test_seguir_metrics_counts_offers_and_mean():
    rows = [_row("a", n_seguir=2), _row("b", n_seguir=0), _row("c", n_seguir=1)]
    out = seguir_metrics(rows)
    assert out["offer_rate"] == pytest.approx(2 / 3)
    assert out["mean_count"] == pytest.approx(1.0)


def test_seguir_agreement_penalises_chips_on_closed_turns():
    """A chip offered where the turn had closed is the failure being measured."""
    rows = [
        _row("open", expects=True, n_seguir=2),
        _row("closed", path="encerramento", expects=False, n_seguir=2),
    ]
    out = seguir_metrics(rows)
    assert out["wrong_offer"] == 1
    assert out["wrong_silence"] == 0
    assert out["agreement"] == 0.5


def test_seguir_agreement_penalises_silence_on_open_topics():
    """Silence is not free: a variant that never offers must not score well."""
    rows = [_row(str(i), expects=True, n_seguir=0) for i in range(4)]
    out = seguir_metrics(rows)
    assert out["offer_rate"] == 0.0
    assert out["wrong_silence"] == 4
    assert out["agreement"] == 0.0


def test_seguir_agreement_ignores_undecided_cases():
    """`expects_seguir: None` is a judgement call — it must not pad the score."""
    rows = [
        _row("judged", expects=True, n_seguir=2),
        _row("free", path="pratica", expects=None, n_seguir=0),
    ]
    out = seguir_metrics(rows)
    assert out["agreement"] == 1.0  # scored over the one judged case only
    assert out["offer_rate"] == 0.5  # but both count toward the raw rate


def test_seguir_metrics_handles_empty_rows():
    out = seguir_metrics([])
    assert out["offer_rate"] == 0.0
    assert out["agreement"] is None


def test_seguir_by_path_separates_the_paths():
    rows = [
        _row("a", path="abertura", n_seguir=2),
        _row("b", path="abertura", n_seguir=0),
        _row("c", path="pessoal", expects=False, n_seguir=2),
    ]
    out = seguir_by_path(rows)
    assert out["abertura"]["n"] == 2
    assert out["abertura"]["offer_rate"] == 0.5
    assert out["pessoal"]["offer_rate"] == 1.0


# --- variants ----------------------------------------------------------------


def test_variants_differ_on_whether_chips_are_mandatory():
    assert "DUAS perguntas" in VARIANTS["duas-sempre"]
    assert "ATÉ duas" in VARIANTS["seguir-opcional"]
    assert "[SEGUIR:] vazio" in VARIANTS["seguir-opcional"]


# --- report ------------------------------------------------------------------


def test_report_shows_every_variant_for_a_case():
    lanes = {
        "duas-sempre": [_row("abertura-espirito", n_seguir=2)],
        "seguir-opcional": [_row("abertura-espirito", n_seguir=0)],
    }
    report = format_report(lanes)
    assert "duas-sempre" in report
    assert "seguir-opcional" in report
    assert "_(nenhum)_" in report  # the silent variant is visible as silence


def test_report_warns_when_only_one_variant_ran():
    report = format_report({"duas-sempre": [_row("abertura-espirito")]})
    assert "não são nada" in report


# --- similarity distribution (source_min_similarity calibration) -------------


def test_similarity_distribution_reports_min_median_percentiles_max():
    out = similarity_distribution([0.1, 0.2, 0.3, 0.4, 0.5])
    assert out["min"] == 0.1
    assert out["median"] == pytest.approx(0.3)
    assert out["max"] == 0.5


def test_similarity_distribution_counts_kept_at_thresholds():
    out = similarity_distribution([0.25, 0.35, 0.45, 0.55, 0.65])
    assert out["kept_at_0.3"] == 4
    assert out["kept_at_0.4"] == 3
    assert out["kept_at_0.5"] == 2
    assert out["kept_at_0.6"] == 1


def test_similarity_distribution_handles_empty():
    out = similarity_distribution([])
    assert out["median"] == 0.0
    assert out["kept_at_0.3"] == 0


# --- truncados (finish_reason) ------------------------------------------------


def test_summarize_counts_truncados():
    rows = [
        _row("a", finish_reason="stop"),
        _row("b", finish_reason="length"),
        _row("c", finish_reason="stop"),
    ]
    out = summarize(rows)
    assert out["truncados"] == 1


def test_summarize_truncados_ignores_none_finish_reason():
    """None means "not captured" (short-circuited turn, or production
    prose_completion ran unpatched) — not a truncation."""
    rows = [_row("a", finish_reason=None), _row("b", finish_reason="stop")]
    out = summarize(rows)
    assert out["truncados"] == 0


def test_summarize_truncados_defaults_to_zero_without_the_key():
    """Rows produced before finish_reason existed must not break summarize."""
    row = _row("a")
    del row["finish_reason"]
    out = summarize([row])
    assert out["truncados"] == 0


def test_summarize_handles_empty_rows_truncados():
    assert summarize([])["truncados"] == 0


def test_format_report_shows_truncados_per_lane():
    lanes = {
        "google:gemini-3.6-flash": [
            _row("a", finish_reason="length"),
            _row("b", finish_reason="stop"),
        ]
    }
    report = format_report(lanes)
    assert "truncados" in report
    assert "1 de 2" in report


# --- lane-name sanitisation ---------------------------------------------------


def test_sanitize_lane_name_replaces_colon_and_slash():
    assert _sanitize_lane_name("google:gemini-3.6-flash") == "google-gemini-3.6-flash"
    assert (
        _sanitize_lane_name("openrouter:deepseek/deepseek-chat")
        == "openrouter-deepseek-deepseek-chat"
    )


def test_sanitize_lane_name_leaves_plain_variant_names_untouched():
    assert _sanitize_lane_name("duas-sempre") == "duas-sempre"


def test_lane_path_uses_sanitized_name():
    assert (
        lane_path("google:gemini-3.6-flash") == "logs/lane-google-gemini-3.6-flash.json"
    )


# --- --variants / --models mutual exclusion -----------------------------------


def test_variants_and_models_together_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_generators.py",
            "--variants",
            "duas-sempre",
            "--models",
            "google:gemini-3.6-flash",
            "--report-only",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    err = capsys.readouterr().err
    assert "cannot be combined" in err


def test_models_entry_without_colon_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["compare_generators.py", "--models", "gemini-3.6-flash", "--report-only"],
    )
    with pytest.raises(SystemExit):
        main()
    err = capsys.readouterr().err
    assert "provider:model" in err


def test_max_tokens_override_reaches_the_call(monkeypatch):
    """A reasoning model spends the budget on thinking before it writes.

    gemini-3.6-flash truncated 23 of 26 answers at the production 1024, and the
    [FONTES]/[SEGUIR] trailer lives at the END of the answer — so the chip
    metrics scored the cut, not the model. The override has to actually reach
    the completion call, or the re-run measures the same thing again.
    """
    seen = {}

    class FakeClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    seen.update(kwargs)
                    from unittest.mock import MagicMock

                    return MagicMock(
                        choices=[
                            MagicMock(
                                finish_reason="stop",
                                message=MagicMock(content="ok"),
                            )
                        ]
                    )

    monkeypatch.setattr(cg, "_pinned_prose_completion", cg._pinned_prose_completion)
    with patch("src.rag.llm_client.get_client", return_value=FakeClient):
        shim = cg._pinned_prose_completion(0.0, None, 4096)
        shim("sys", [{"role": "user", "content": "q"}])
    assert seen["max_tokens"] == 4096

    with patch("src.rag.llm_client.get_client", return_value=FakeClient):
        shim = cg._pinned_prose_completion(0.0, None, None)
        shim("sys", [{"role": "user", "content": "q"}])
    assert seen["max_tokens"] == 1024, "sem override, o valor de produção manda"


def test_truncation_warning_names_the_lane_and_the_reason():
    """A silent `truncados: 23` in a stats dict is a number nobody reads."""
    rows = [
        {
            "id": "x",
            "path": "abertura",
            "question": "q",
            "expects_seguir": True,
            "answer": "a",
            "seguir": [],
            "n_seguir": 0,
            "groundedness": 0.5,
            "confiavel": True,
            "finish_reason": "length",
        }
    ]
    report = cg.format_report({"google-gemini-3.6-flash": rows})
    assert "google-gemini-3.6-flash (1)" in report
    assert "truncad" in report.lower()
    assert "--max-tokens" in report
