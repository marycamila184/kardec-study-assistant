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


@pytest.mark.parametrize(
    "name,assembled", _cases(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_assembled_prompt_matches_the_recorded_baseline(name, assembled):
    """Byte-identical to what the code produced before the profile existed."""
    recorded = (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")
    assert assembled == recorded


def test_no_baseline_case_disappeared():
    """A case dropped from the capture script would silently stop being checked."""
    recorded = {p.stem for p in FIXTURES.glob("*.txt")}
    assert {name for name, _ in _cases()} == recorded


def test_render_instructions_is_empty_for_both_presets():
    """The whole reason the prompts can be unchanged."""
    assert render_instructions(CHAT_DEFAULT) == ""
    assert render_instructions(STUDY_DEFAULT) == ""


def test_render_instructions_is_empty_for_any_profile_today():
    """Step 1 is inert for every value, not only the presets — the dimensions
    exist as fields before they do anything."""
    loud = ResponseProfile(
        citation_style="inline",
        depth="aprofundado",
        vocabulary="tecnico",
        answer_format="topicos",
        extra="cite tudo",
    )
    assert render_instructions(loud) == ""


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
