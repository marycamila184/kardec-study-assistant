"""Inline grounding markers.

The invariant these tests exist for: a marker naming something that was not
retrieved never reaches the reader. An inline citation invites verification, so
a fabricated one is worse than none.

See docs/superpowers/specs/2026-07-28-grounding-markers-design.md
"""

from src.rag.inline_refs import extract_item_refs, extract_passage_refs

_ALLOWED = [
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter_title": "MUITOS OS CHAMADOS",
        "item_number": "11",
        "excerpt": "11. Vim a este mundo para exercer um juízo.",
    },
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter_title": "MUITOS OS CHAMADOS",
        "item_number": "2",
        "excerpt": "2. O incrédulo sorri a esta parábola.",
    },
]

_CHUNKS = [
    {
        "content": "A encarnação tem por fim fazê-los progredir.",
        "metadata": {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Encarnação",
            "item_number": "132",
        },
    },
    {
        "content": "Fora da caridade não há salvação.",
        "metadata": {
            "book": "O Evangelho Segundo o Espiritismo",
            "chapter_title": "Fora da Caridade",
            "item_number": "4",
        },
    },
]


# ── /study: [item N] ──────────────────────────────────────────────────────────


def test_resolved_marker_becomes_a_reference_and_leaves_the_prose_clean():
    clean, refs = extract_item_refs(
        "O julgamento retorna sobre quem julga [item 11], como Kardec explica.",
        _ALLOWED,
    )
    assert clean == "O julgamento retorna sobre quem julga, como Kardec explica."
    assert len(refs) == 1
    assert refs[0]["item_number"] == "11"
    assert refs[0]["excerpt"].startswith("11. Vim a este mundo")


def test_marker_for_an_item_never_retrieved_is_dropped():
    """The rule the whole module exists for."""
    clean, refs = extract_item_refs(
        "Kardec trata disso em outro lugar [item 999].", _ALLOWED
    )
    assert clean == "Kardec trata disso em outro lugar."
    assert refs == []


def test_a_dropped_marker_leaves_no_scar():
    """It must not read as though something was censored."""
    clean, _ = extract_item_refs("Uma frase [item 999] no meio.", _ALLOWED)
    assert clean == "Uma frase no meio."
    assert "[" not in clean and "]" not in clean


def test_position_points_into_the_clean_text():
    clean, refs = extract_item_refs("Início [item 2] fim.", _ALLOWED)
    assert refs[0]["position"] <= len(clean)
    assert clean[: refs[0]["position"]] == "Início"


def test_several_markers_keep_their_order():
    clean, refs = extract_item_refs("Primeiro [item 2], depois [item 11].", _ALLOWED)
    assert [r["item_number"] for r in refs] == ["2", "11"]
    assert "item" not in clean


def test_case_and_spacing_variants_are_tolerated():
    for written in ("[item 11]", "[ITEM 11]", "[ item  11 ]", "[Item11]"):
        _, refs = extract_item_refs(f"Texto {written}.", _ALLOWED)
        assert len(refs) == 1, written


def test_a_bare_bracketed_number_is_not_an_item_marker():
    """/study prose can legitimately contain brackets; guessing would strip a
    reader's own text."""
    clean, refs = extract_item_refs("Uma nota [11] do editor.", _ALLOWED)
    assert clean == "Uma nota [11] do editor."
    assert refs == []


def test_text_without_markers_is_untouched():
    original = "Uma explicação inteiramente sem marcadores."
    clean, refs = extract_item_refs(original, _ALLOWED)
    assert clean == original
    assert refs == []


def test_empty_text():
    assert extract_item_refs("", _ALLOWED) == ("", [])


def test_no_allowed_items_drops_everything():
    clean, refs = extract_item_refs("Texto [item 11].", [])
    assert clean == "Texto."
    assert refs == []


# ── /chat: [fonte N] ────────────────────────────────────────────────────────────────


def test_passage_index_resolves_to_its_chunk():
    clean, refs = extract_passage_refs("A encarnação faz progredir [fonte 1].", _CHUNKS)
    assert clean == "A encarnação faz progredir."
    assert refs[0]["book"] == "O Livro dos Espíritos"
    assert refs[0]["item_number"] == "132"


def test_index_outside_the_retrieved_list_is_dropped():
    clean, refs = extract_passage_refs("Uma afirmação [fonte 7].", _CHUNKS)
    assert clean == "Uma afirmação."
    assert refs == []


def test_one_marker_may_carry_several_indices():
    _, refs = extract_passage_refs("Ambas dizem isso [fonte 1, 2].", _CHUNKS)
    assert [r["item_number"] for r in refs] == ["132", "4"]


def test_a_partly_valid_marker_keeps_only_what_was_retrieved():
    _, refs = extract_passage_refs("Texto [fonte 1, 9].", _CHUNKS)
    assert [r["item_number"] for r in refs] == ["132"]


def test_a_bare_bracketed_number_is_not_a_passage_marker():
    """The reason the word is there: brackets around numbers occur in ordinary
    prose and in the works."""
    clean, refs = extract_passage_refs("Uma nota [1] do editor.", _CHUNKS)
    assert clean == "Uma nota [1] do editor."
    assert refs == []
