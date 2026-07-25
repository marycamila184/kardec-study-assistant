from scripts.compare_generators import (
    format_report,
    format_study_report,
    similarity_distribution,
    summarize,
    summarize_study,
)


def test_summarize_averages_metrics():
    rows = [
        {"question": "q1", "answer": "a1", "groundedness": 0.8, "confiavel": True},
        {"question": "q2", "answer": "a2", "groundedness": 0.6, "confiavel": False},
    ]
    out = summarize(rows)
    assert out["mean_groundedness"] == 0.7
    assert out["hallucinated_citation_rate"] == 0.5


def test_summarize_handles_empty_rows():
    out = summarize([])
    assert out["mean_groundedness"] == 0.0
    assert out["hallucinated_citation_rate"] == 0.0


def test_report_contains_both_lanes_side_by_side():
    report = format_report(
        [
            {
                "question": "o que é o espírito?",
                "prose": {
                    "answer": "resposta A",
                    "groundedness": 0.8,
                    "confiavel": True,
                },
                "json": {
                    "answer": "resposta B",
                    "groundedness": 0.7,
                    "confiavel": True,
                },
            }
        ]
    )
    assert "o que é o espírito?" in report
    assert "resposta A" in report
    assert "resposta B" in report


# --- /study coverage (Finding 1) --------------------------------------------


def test_summarize_study_computes_failure_rate():
    rows = [
        {
            "book": "b",
            "item_number": "1",
            "contexto": "c1",
            "conceitos_chave": [],
            "generation_failed": True,
            "groundedness": 0.0,
        },
        {
            "book": "b",
            "item_number": "2",
            "contexto": "c2",
            "conceitos_chave": [],
            "generation_failed": False,
            "groundedness": 0.6,
        },
    ]
    out = summarize_study(rows)
    assert out["study_failure_rate"] == 0.5


def test_summarize_study_handles_empty_rows():
    out = summarize_study([])
    assert out["study_failure_rate"] == 0.0


def test_marker_failure_is_counted_separately_from_user_visible_failure():
    """The 2026-07-25 regression in reading: the fallback rescued all three
    items, so study_failure_rate read 0.0 while the prose model had honored the
    marker contract exactly zero times."""
    rows = [
        {"generation_failed": False, "marker_failed": True},
        {"generation_failed": False, "marker_failed": True},
    ]
    out = summarize_study(rows)
    assert out["study_failure_rate"] == 0.0
    assert out["marker_failure_rate"] == 1.0


def test_report_flags_fallback_text_as_not_riv_ai():
    """A contexto written by the fallback must never read as prose-lane output."""
    report = format_study_report(
        [
            {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "prose": {
                    "contexto": "escrito pelo 70B",
                    "conceitos_chave": [],
                    "generation_failed": False,
                    "marker_failed": True,
                    "groundedness": 0.7,
                },
                "json": {
                    "contexto": "c",
                    "conceitos_chave": [],
                    "generation_failed": False,
                    "groundedness": 0.5,
                },
            }
        ]
    )
    assert "70B fallback" in report


def test_format_study_report_contains_item_and_both_lanes():
    report = format_study_report(
        [
            {
                "book": "O Livro dos Espíritos",
                "item_number": "625",
                "prose": {
                    "contexto": "contexto A",
                    "conceitos_chave": ["dever: obrigação"],
                    "generation_failed": False,
                    "groundedness": 0.7,
                },
                "json": {
                    "contexto": "contexto B",
                    "conceitos_chave": [],
                    "generation_failed": True,
                    "groundedness": 0.5,
                },
            }
        ]
    )
    assert "O Livro dos Espíritos" in report
    assert "625" in report
    assert "contexto A" in report
    assert "contexto B" in report
    assert "dever: obrigação" in report


# --- similarity distribution (Finding 3) ------------------------------------


def test_similarity_distribution_reports_min_median_percentiles_max():
    out = similarity_distribution([0.1, 0.2, 0.3, 0.4, 0.5])
    assert out["min"] == 0.1
    assert out["max"] == 0.5
    assert out["median"] == 0.3


def test_similarity_distribution_counts_kept_at_thresholds():
    out = similarity_distribution([0.2, 0.35, 0.45, 0.55, 0.65])
    assert out["kept_at_0.3"] == 4
    assert out["kept_at_0.4"] == 3
    assert out["kept_at_0.5"] == 2
    assert out["kept_at_0.6"] == 1


def test_similarity_distribution_handles_empty():
    out = similarity_distribution([])
    assert out["min"] == 0.0
    assert out["max"] == 0.0
    assert out["kept_at_0.3"] == 0
