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
