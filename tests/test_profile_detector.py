"""Reading a message for a request about the shape of the answer.

The pinning rules are the part worth protecting: a dimension the reader asked
for must not be quietly taken back when the conversation lightens.
"""

from src.rag.profile import CHAT_DEFAULT
from src.rag.profile_detector import apply_changes


def test_an_explicit_request_changes_and_pins_the_dimension():
    out = apply_changes(CHAT_DEFAULT, {"citacao": "inline"})
    assert out.citation_style == "inline"
    assert "citation_style" in out.pinned


def test_two_dimensions_at_once():
    out = apply_changes(CHAT_DEFAULT, {"citacao": "inline", "referencia": "full"})
    assert out.citation_style == "inline"
    assert out.citation_precision == "full"
    assert out.pinned == frozenset({"citation_style", "citation_precision"})


def test_an_ordinary_question_changes_nothing():
    assert apply_changes(CHAT_DEFAULT, {}) is CHAT_DEFAULT


def test_a_value_outside_the_vocabulary_is_ignored():
    """A classifier that invents a value must not reshape the answer."""
    assert apply_changes(CHAT_DEFAULT, {"citacao": "colorido"}) is CHAT_DEFAULT


def test_asking_for_what_is_already_set_does_not_re_pin():
    assert apply_changes(CHAT_DEFAULT, {"citacao": "chips"}) is CHAT_DEFAULT


def test_pins_accumulate_across_turns():
    first = apply_changes(CHAT_DEFAULT, {"citacao": "inline"})
    second = apply_changes(first, {"referencia": "full"})
    assert second.pinned == frozenset({"citation_style", "citation_precision"})
    assert second.citation_style == "inline"


def test_a_later_explicit_request_can_change_a_pinned_dimension():
    """Only another explicit request moves it — that is what 'pinned' means."""
    pinned = apply_changes(CHAT_DEFAULT, {"citacao": "inline"})
    changed = apply_changes(pinned, {"citacao": "none"})
    assert changed.citation_style == "none"
    assert "citation_style" in changed.pinned


def test_the_incoming_profile_is_never_mutated():
    before = apply_changes(CHAT_DEFAULT, {"citacao": "inline"})
    apply_changes(before, {"referencia": "full"})
    assert before.citation_precision == "short"
    assert CHAT_DEFAULT.citation_style == "chips"


# ── The inferred level ────────────────────────────────────────────────────────


def test_the_level_moves_one_step_at_a_time():
    """A jump from neutral to technical between two turns is exactly the seam
    this is meant not to have."""
    from src.rag.profile import ResponseProfile
    from src.rag.profile_detector import apply_level, current_level

    light = ResponseProfile(depth="breve", vocabulary="iniciante")
    assert current_level(light) == 0

    once = apply_level(light, 2)
    assert current_level(once) == 1, "must not jump two levels in one turn"

    twice = apply_level(once, 2)
    assert current_level(twice) == 2


def test_depth_and_vocabulary_move_together():
    """Inferring them separately would allow 'aprofundado + iniciante', which is
    not a reader but a contradiction."""
    from src.rag.profile_detector import apply_level

    out = apply_level(CHAT_DEFAULT, 2)
    assert (out.depth, out.vocabulary) == ("aprofundado", "tecnico")


def test_going_down_is_just_as_gradual():
    """One basic question does not reset a conversation."""
    from src.rag.profile import ResponseProfile
    from src.rag.profile_detector import apply_level, current_level

    deep = ResponseProfile(depth="aprofundado", vocabulary="tecnico")
    assert current_level(apply_level(deep, 0)) == 1


def test_a_pinned_dimension_ignores_the_level():
    """An inference is not an argument against a request."""
    from src.rag.profile import ResponseProfile
    from src.rag.profile_detector import apply_level

    pinned = ResponseProfile(pinned=frozenset({"vocabulary"}))
    out = apply_level(pinned, 2)
    assert out.depth == "aprofundado"
    assert out.vocabulary == "corrente", "pinned dimension must not follow"


def test_staying_at_the_same_level_changes_nothing():
    from src.rag.profile_detector import apply_level

    assert apply_level(CHAT_DEFAULT, 1) is CHAT_DEFAULT


def test_an_out_of_range_level_is_clamped_not_crashed():
    from src.rag.profile_detector import apply_level, current_level

    assert current_level(apply_level(CHAT_DEFAULT, 99)) == 2
    assert current_level(apply_level(CHAT_DEFAULT, -5)) == 0


def test_an_explicit_request_still_wins_over_the_level():
    """Both arrive in the same classifier reply; the request pins, the level
    moves what is left."""
    from src.rag.profile_detector import apply_changes, apply_level

    asked = apply_changes(CHAT_DEFAULT, {"citacao": "inline"})
    moved = apply_level(asked, 2)
    assert moved.citation_style == "inline"
    assert "citation_style" in moved.pinned
    assert moved.depth == "aprofundado"


def test_a_doctrinal_question_is_not_a_request_about_form():
    """Measured 2026-07-28: 'o que Kardec diz sobre a prece?' was setting
    citation_style to inline — and an explicit request PINS, so a shape nobody
    asked for would stick to the whole conversation. Two of five plain
    questions tripped it before the classifier learned the difference.

    The pure half is tested here; the classifier prompt carries the example.
    """
    for asked in ({}, {"nivel": "medio"}):
        assert apply_changes(CHAT_DEFAULT, asked) is CHAT_DEFAULT


def test_the_study_mode_starts_deeper_than_a_first_question_elsewhere():
    """Someone who opened Estudar has already said what they came for."""
    from src.rag.profile import MODE_DEFAULTS

    study = MODE_DEFAULTS["estudar_obra"]
    assert study.depth == "aprofundado"
    assert study.citation_style == "inline"
    # Deep is not technical: a newcomer can open Estudar, and the product exists
    # to lower that barrier.
    assert study.vocabulary == "corrente"


def test_the_study_depth_survives_the_level_classifier():
    """aprofundado + corrente matches no paired level, so an unpinned depth
    would read as neutral and get pulled back down on the next turn."""
    from src.rag.profile import MODE_DEFAULTS
    from src.rag.profile_detector import apply_level

    study = MODE_DEFAULTS["estudar_obra"]
    assert apply_level(study, 0).depth == "aprofundado"


def test_an_explicit_request_still_overrides_the_mode_default():
    from src.rag.profile import MODE_DEFAULTS

    study = MODE_DEFAULTS["estudar_obra"]
    assert apply_changes(study, {"citacao": "none"}).citation_style == "none"
