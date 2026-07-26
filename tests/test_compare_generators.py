import pytest

from scripts.compare_generators import (
    VARIANTS,
    format_report,
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
    assert "DUAS perguntas" in VARIANTS["atual"]
    assert "ATÉ duas" in VARIANTS["seguir-opcional"]
    assert "[SEGUIR:] vazio" in VARIANTS["seguir-opcional"]


# --- report ------------------------------------------------------------------


def test_report_shows_every_variant_for_a_case():
    lanes = {
        "atual": [_row("abertura-espirito", n_seguir=2)],
        "seguir-opcional": [_row("abertura-espirito", n_seguir=0)],
    }
    report = format_report(lanes)
    assert "atual" in report
    assert "seguir-opcional" in report
    assert "_(nenhum)_" in report  # the silent variant is visible as silence


def test_report_warns_when_only_one_variant_ran():
    report = format_report({"atual": [_row("abertura-espirito")]})
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
