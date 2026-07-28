"""The profile seam is inert.

Step 1 threads a ResponseProfile through prompt assembly and must change
nothing. These tests are the proof, and they compare against fixtures recorded
from the pre-refactor code (scripts/capture_prompt_baseline.py) — comparing the
refactor against itself would prove only that it agrees with itself.

See docs/superpowers/specs/2026-07-28-profile-seam-design.md
"""

import dataclasses
import pathlib

import pytest

from scripts.capture_prompt_baseline import capture
from src.rag.profile import (
    CHAT_DEFAULT,
    STUDY_DEFAULT,
    ResponseProfile,
    render_instructions,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "prompt_baseline"


def _cases():
    return sorted(capture().items())


@pytest.mark.parametrize("name", sorted(capture()))
def test_assembled_prompt_matches_the_recorded_baseline(name):
    """Byte-identical to the recorded baseline.

    Parametrised over names alone: the assembled prompt is a whole system
    prompt, and putting it in the test id makes a failure unreadable.
    """
    recorded = (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")
    assert capture()[name] == recorded


def test_no_baseline_case_disappeared():
    """A case dropped from the capture script would silently stop being checked."""
    recorded = {p.stem for p in FIXTURES.glob("*.txt")}
    assert {name for name, _ in _cases()} == recorded


def test_render_instructions_is_empty_for_both_presets():
    """The whole reason the prompts can be unchanged."""
    assert render_instructions(CHAT_DEFAULT) == ""
    assert render_instructions(STUDY_DEFAULT) == ""


def test_a_dimension_at_its_default_renders_nothing():
    """The base prompt already says what the default means; a second,
    differently-worded copy of a rule the model already has is a liability.

    Written with the actual defaults: the earlier version used non-default depth
    and vocabulary and passed only because neither rendered anything yet.
    """
    quiet = ResponseProfile(depth="normal", vocabulary="corrente")
    assert render_instructions(quiet) == ""


def test_each_dimension_renders_only_its_own_instruction():
    assert "parágrafo curto" in render_instructions(ResponseProfile(depth="breve"))
    assert "parágrafo curto" not in render_instructions(
        ResponseProfile(vocabulary="iniciante")
    )


def test_leaving_the_default_renders_an_instruction():
    """Step 3 makes the seam do work. Step 1's guarantee survives as the
    narrower one above: unchanged dimensions still add nothing."""
    rendered = render_instructions(ResponseProfile(citation_style="inline"))
    assert "[fonte N]" in rendered


def test_citation_precision_does_not_touch_the_prompt_at_all():
    """It is not a prompt concern. Asking the model to write references failed
    twice on 2026-07-28 — once contradicted by a stronger rule, and once with
    that contradiction removed, still zero. What works is the model marking
    WHERE the reference goes and code writing the canonical form from metadata.

    So the prompt is identical for both values, and the model is told the same
    thing in every profile: never write a reference into the prose.
    """
    import dataclasses

    from src.rag.prompt import build_messages

    full = dataclasses.replace(CHAT_DEFAULT, citation_precision="full")
    assert render_instructions(full) == ""

    short_prompt, _ = build_messages("q", [], [], profile=CHAT_DEFAULT)
    full_prompt, _ = build_messages("q", [], [], profile=full)

    assert short_prompt == full_prompt
    assert "Não escreva referências bibliográficas" in short_prompt


def test_a_profile_is_immutable():
    """A shared mutable default would let one request's shape leak into the
    next — invisible until a confused reader reports it."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        CHAT_DEFAULT.depth = "aprofundado"


def test_deriving_a_variant_leaves_the_preset_untouched():
    variant = dataclasses.replace(CHAT_DEFAULT, depth="aprofundado")
    assert variant.depth == "aprofundado"
    assert CHAT_DEFAULT.depth == "normal"


def test_presets_record_what_each_mode_does_today():
    assert CHAT_DEFAULT.answer_format == "prosa"
    assert CHAT_DEFAULT.citation_style == "chips"
    assert STUDY_DEFAULT.answer_format == "estruturado"
    assert "conceitos" in STUDY_DEFAULT.sections
