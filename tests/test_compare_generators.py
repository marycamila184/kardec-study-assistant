from scripts.compare_generators import format_report, summarize


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
