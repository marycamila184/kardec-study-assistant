"""`expand_to_item` — the /chat hit carrying the item around it.

The behaviours pinned here are the ones the design paid for: the window grows
from the HIT and not from the item's opening, `content` survives untouched so
the source chip keeps showing what won retrieval, and the two guards that read
the expanded text (the quote haystack and the sensitivity filter) see it.
"""

from unittest.mock import MagicMock

import pytest

from src.rag.quote_check import find_unsupported_quotes
from src.rag.retriever import (
    expand_to_item,
    filter_sensitive_chunks,
    prompt_text,
)

BOOK = "O Livro dos Médiuns"


def _sub(index: int, content: str, total: int = 3, item: str = "7", **meta) -> dict:
    return {
        "content": content,
        "metadata": {
            "book": BOOK,
            "part": "PRIMEIRA PARTE",
            "chapter": "CAPÍTULO II",
            "chapter_title": "DO MARAVILHOSO E DO SOBRENATURAL",
            "item_number": item,
            "subchunk_index": index,
            "total_subchunks": total,
            "starts_paragraph": True,
            **meta,
        },
        "distance": 0.3,
    }


# The real item: subchunk 2 opens mid-sentence, and its subject is in subchunk 1.
ITEM_7 = [
    _sub(1, "7. Se a crença nos Espíritos representasse uma concepção singular,"),
    _sub(2, "que não é, nem pode ser uma destas leis.", starts_paragraph=False),
    _sub(3, "O pensamento é um dos atributos do Espírito;"),
]


@pytest.fixture
def store(monkeypatch):
    mock = MagicMock()
    mock.get_by_filter.return_value = [
        dict(c, metadata=dict(c["metadata"])) for c in ITEM_7
    ]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock)
    return mock


def test_window_grows_backwards_first_when_only_one_neighbour_fits(store):
    """The failure this feature exists for. The hit is 40 chars, its predecessor
    67 and its successor 44; at 110 each fits beside the hit but not both, and
    the PREDECESSOR is the one that must win — the subject of "que não é" is
    there. Growing from the item's opening would have picked this text for the
    wrong reason; growing forward would leave the clause dangling."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=110)

    text = prompt_text(expanded)
    assert text.startswith("7. Se a crença")
    assert "que não é" in text
    assert "O pensamento" not in text


def test_budget_still_buys_the_successor_when_the_predecessor_will_not_fit(store):
    """Preference for the predecessor is not a veto. At 100 the 67-char
    predecessor does not fit beside the 40-char hit and the 44-char successor
    does — spending the budget beats leaving it unspent, since more of the item
    is the point even when the opening stays cut."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=100)

    text = prompt_text(expanded)
    assert text.startswith("que não é")
    assert "O pensamento" in text


def test_whole_item_when_it_fits(store):
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=3000)

    text = prompt_text(expanded)
    assert text.startswith("7. Se a crença")
    assert text.endswith("atributos do Espírito;")


def test_content_is_never_mutated(store):
    """The source chip reads `content`, and the reader must keep seeing the
    subchunk that actually won retrieval — expansion is prompt-only."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=3000)

    assert expanded["content"] == "que não é, nem pode ser uma destas leis."


def test_hit_survives_a_cap_smaller_than_itself(store):
    """Never drop to empty — the same rule chapter_commentary follows."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=1)

    assert prompt_text(expanded) == "que não é, nem pode ser uma destas leis."


def test_single_subchunk_item_needs_no_lookup(store):
    """Half the corpus's numbered items are one subchunk; expansion there is a
    no-op and must not cost a query."""
    hit = _sub(1, "341. A alma é o Espírito encarnado.", total=1, item="341")
    (expanded,) = expand_to_item([hit])

    assert prompt_text(expanded) == "341. A alma é o Espírito encarnado."
    store.get_by_filter.assert_not_called()


def test_two_subchunks_of_one_item_collapse_to_one_passage(store):
    """Otherwise the prompt prints the same item twice under two numbers."""
    hits = [
        dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"])),
        dict(ITEM_7[2], metadata=dict(ITEM_7[2]["metadata"])),
    ]
    expanded = expand_to_item(hits, char_cap=3000)

    assert len(expanded) == 1
    assert expanded[0]["content"] == "que não é, nem pode ser uma destas leis."


def test_distinct_items_are_kept_in_retrieval_order(store):
    """`append_chapter_commentary` and the [fonte N] numbering both depend on
    chunks[0] still being the top hit."""
    other = _sub(1, "outro item", total=1, item="9")
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    expanded = expand_to_item([hit, other], char_cap=3000)

    assert [c["metadata"]["item_number"] for c in expanded] == ["7", "9"]


def test_sibling_lookup_failure_degrades_to_the_subchunk(monkeypatch):
    """A retrieval problem here must cost the context, never the answer."""
    mock = MagicMock()
    mock.get_by_filter.side_effect = RuntimeError("chroma down")
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock)

    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    (expanded,) = expand_to_item([hit], char_cap=3000)

    assert prompt_text(expanded) == "que não é, nem pode ser uma destas leis."


def test_part_is_in_the_sibling_lookup(store):
    """O Céu e o Inferno restarts item numbering per part: (book, chapter, item)
    matches CAPÍTULO I item 1 in BOTH parts, which are different passages."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    expand_to_item([hit], char_cap=3000)

    conditions = store.get_by_filter.call_args[0][0]["$and"]
    assert {"part": {"$eq": "PRIMEIRA PARTE"}} in conditions


def test_quote_guard_accepts_a_quotation_from_an_expanded_neighbour(store):
    """The regression that would discard whole correct answers: the model reads
    the expanded item, quotes a neighbouring subchunk correctly, and a haystack
    built from `content` alone calls it fabrication."""
    hit = dict(ITEM_7[1], metadata=dict(ITEM_7[1]["metadata"]))
    expanded = expand_to_item([hit], char_cap=3000)

    answer = 'Kardec escreve que "O pensamento é um dos atributos do Espírito".'
    assert find_unsupported_quotes(answer, expanded) == []


def test_sensitivity_filter_sees_the_expanded_text(store, monkeypatch):
    """The deterministic floor. Suicide-adjacent language in a neighbouring
    subchunk reaches the prompt too, so the abalo filter has to look at it."""
    siblings = [
        _sub(1, "texto doutrinário comum."),
        _sub(2, "quem comete suicídio nada resolve.", starts_paragraph=False),
    ]
    mock = MagicMock()
    mock.get_by_filter.return_value = siblings
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock)

    hit = dict(siblings[0], metadata=dict(siblings[0]["metadata"]))
    expanded = expand_to_item([hit], char_cap=3000)

    assert "suicíd" in prompt_text(expanded[0])
    assert filter_sensitive_chunks(expanded) == []
