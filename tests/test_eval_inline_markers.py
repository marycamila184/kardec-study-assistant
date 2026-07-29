"""The marker evaluation's own arithmetic.

The script needs a provider and a populated index to run; these tests cover the
measurement, which is what a decision would be made on.

See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
"""

from scripts.eval_inline_markers import _measure, summarize

_CASE = {"id": "caso"}
_AVAILABLE = [
    {"book": "ESE", "chapter_title": "C", "item_number": "2", "excerpt": "dois"},
    {"book": "ESE", "chapter_title": "C", "item_number": "11", "excerpt": "onze"},
]


def test_counts_written_resolved_and_invented():
    row = _measure(
        _CASE,
        "Uma afirmação [item 2] e outra [item 999] e mais uma [item 11].",
        _AVAILABLE,
    )
    assert row["markers_written"] == 3
    assert row["invented"] == 1
    assert row["invented_numbers"] == ["999"]
    assert row["refs_resolved"] == 2
    assert row["distinct_cited"] == 2


def test_no_marker_ever_reaches_the_reader():
    """The invariant the whole module exists to protect."""
    row = _measure(_CASE, "Texto [item 2] e [item 999].", _AVAILABLE)
    assert row["markers_reaching_reader"] == 0


def test_invented_rate_is_over_markers_written_not_over_cases():
    rows = [
        _measure(_CASE, "a [item 2] b [item 999].", _AVAILABLE),
        _measure(_CASE, "c [item 11].", _AVAILABLE),
    ]
    s = summarize(rows)
    assert s["invented_rate"] == round(1 / 3, 3)
    assert s["cases_with_any_marker"] == "2/2"


def test_a_model_that_writes_nothing_is_visible():
    """A silently ignored rule looks like success to the code — the numbers are
    the only place it shows."""
    rows = [_measure(_CASE, "Uma explicação sem marcador nenhum.", _AVAILABLE)]
    s = summarize(rows)
    assert s["cases_with_any_marker"] == "0/1"
    assert s["markers_per_answer"] == 0.0
    assert s["coverage"] == 0.0
    assert s["invented_rate"] == 0.0


def test_no_division_by_zero_when_nothing_is_available():
    rows = [_measure(_CASE, "Sem comentário disponível.", [])]
    assert summarize(rows)["coverage"] == 0.0


def test_tail_clumping_spots_markers_dumped_at_the_end():
    body = "Uma frase longa o suficiente para dar corpo ao texto todo. " * 3
    clumped = _measure(_CASE, body + "[item 2][item 11]", _AVAILABLE)
    assert summarize([clumped])["tail_clumping"] == 1.0

    spread = _measure(_CASE, "Começo [item 2]. " + body + " fim.", _AVAILABLE)
    assert summarize([spread])["tail_clumping"] == 0.0
