"""The expansion A/B harness's own arithmetic and reporting.

No network and no model: these cover the parts that decide what the run means,
so a misread report cannot be blamed on the metric code.
"""

import json

from scripts.compare_expansion import (
    _is_fragment,
    answer_similarities,
    format_report,
    lane_path,
    load_lane,
    save_lane,
    summarize,
)


def _row(**overrides) -> dict:
    row = {
        "id": "caso",
        "question": "o que é o espírito?",
        "answer": "resposta",
        "not_found": False,
        "n_sources": 2,
        "groundedness": 0.5,
        "confiavel": True,
        "is_fragment": True,
        "prompt_chars": 1000,
        "finish_reason": "stop",
        "seconds": 2.0,
    }
    row.update(overrides)
    return row


def test_summarize_averages_the_lane():
    rows = [_row(groundedness=0.4), _row(groundedness=0.6, prompt_chars=3000)]
    result = summarize(rows)

    assert result["n"] == 2
    assert result["mean_groundedness"] == 0.5
    assert result["mean_prompt_chars"] == 2000.0


def test_summarize_handles_an_empty_lane():
    assert summarize([])["n"] == 0
    assert summarize([])["mean_groundedness"] == 0.0


def test_withheld_counts_answers_lost_to_not_found():
    """Metric 4 — the quote-guard alarm. A withheld answer is not a low score,
    it is a reader who got "não encontrei" instead of a correct answer."""
    rows = [_row(), _row(not_found=True), _row(not_found=True)]

    assert summarize(rows)["withheld"] == 2


def test_prompt_chars_ignores_turns_that_never_called_the_model():
    """Smalltalk and the crisis exit short-circuit before prose_completion, so
    their prompt size is None — averaging it in as zero would understate the
    cost this metric exists to measure."""
    rows = [_row(prompt_chars=2000), _row(prompt_chars=None)]

    assert summarize(rows)["mean_prompt_chars"] == 2000.0


def test_truncados_does_not_count_a_missing_finish_reason():
    rows = [_row(finish_reason=None), _row(finish_reason="length")]

    assert summarize(rows)["truncados"] == 1


def test_is_fragment_reads_total_subchunks_of_the_top_hit():
    whole = [{"metadata": {"total_subchunks": 1}}]
    split = [{"metadata": {"total_subchunks": 4}}]

    assert _is_fragment(split) is True
    assert _is_fragment(whole) is False
    assert _is_fragment([]) is False


def test_is_fragment_treats_missing_metadata_as_whole():
    """Chapter commentary chunks do not carry the full metadata, and a KeyError
    in a reporting split must never lose a finished run."""
    assert _is_fragment([{"metadata": {}}]) is False


def test_answer_similarities_pairs_the_lanes_by_case_id(monkeypatch):
    """The two lanes are embedded in one call, baseline block then expanded
    block; pairing them by position is what makes the cosine per case correct."""
    vectors = {
        "a-base": [1.0, 0.0],
        "b-base": [0.0, 1.0],
        "a-exp": [1.0, 0.0],
        "b-exp": [1.0, 0.0],
    }
    monkeypatch.setattr(
        "src.ingestion.embeddings.encode",
        lambda texts: [vectors[t] for t in texts],
    )

    sims = answer_similarities(
        {
            "baseline": [_row(id="a", answer="a-base"), _row(id="b", answer="b-base")],
            "expanded": [_row(id="a", answer="a-exp"), _row(id="b", answer="b-exp")],
        }
    )

    assert sims["a"] == 1.0
    assert sims["b"] == 0.0


def test_answer_similarities_is_empty_when_only_one_lane_ran():
    assert answer_similarities({"baseline": [_row()]}) == {}


def test_report_flags_withheld_answers_with_their_lane():
    """A retention that appears only in the expanded lane settles the run, so it
    cannot be left to be spotted in a table of averages."""
    report = format_report(
        {"baseline": [_row()], "expanded": [_row(not_found=True)]}, {}
    )

    assert "Respostas retidas" in report
    assert "`expanded`" in report


def test_report_omits_the_warning_when_nothing_was_withheld():
    report = format_report({"baseline": [_row()], "expanded": [_row()]}, {})

    assert "Respostas retidas" not in report


def test_report_splits_by_fragment_shape():
    report = format_report(
        {"expanded": [_row(is_fragment=True), _row(is_fragment=False)]}, {}
    )

    assert "fragmento" in report
    assert "item inteiro" in report


def test_lane_round_trips_through_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.compare_expansion.LANE_DIR", str(tmp_path))
    rows = [_row()]

    save_lane("expanded", rows)

    assert load_lane("expanded") == rows
    assert json.loads(open(lane_path("expanded"), encoding="utf-8").read())["lane"] == (
        "expanded"
    )


def test_load_lane_returns_none_before_a_run(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.compare_expansion.LANE_DIR", str(tmp_path))

    assert load_lane("baseline") is None
