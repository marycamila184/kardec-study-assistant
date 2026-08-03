import datetime

from src.rag.evangelho import _select_passage, get_daily_passage

_SINGLE_CHUNK = [
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO I",
        "chapter_title": "Bem-aventuranças",
        "item_number": "section-4",
        "subchunk_index": 1,
        "total_subchunks": 1,
        "content": "Bem-aventurados os puros de coração.",
        "footnotes": [],
    }
]

_TWO_ITEMS_TWO_CHAPTERS = [
    _SINGLE_CHUNK[0],
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO II",
        "chapter_title": "Amor ao próximo",
        "item_number": "section-7",
        "subchunk_index": 1,
        "total_subchunks": 1,
        "content": "Amai-vos uns aos outros.",
        "footnotes": [],
    },
]

_MULTI_SUBCHUNK_ITEM = [
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO I",
        "chapter_title": "Título Um",
        "item_number": "1",
        "subchunk_index": 3,
        "total_subchunks": 3,
        "content": "Parte C",
        "starts_paragraph": False,
        "footnotes": [],
    },
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO I",
        "chapter_title": "Título Um",
        "item_number": "1",
        "subchunk_index": 1,
        "total_subchunks": 3,
        "content": "Parte A",
        "footnotes": [],
    },
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO I",
        "chapter_title": "Título Um",
        "item_number": "1",
        "subchunk_index": 2,
        "total_subchunks": 3,
        "content": "Parte B",
        "starts_paragraph": False,
        "footnotes": [],
    },
]

_TWO_SUBSECTIONS_SAME_CHAPTER = [
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO XXVII",
        "chapter_title": "Pedi e obtereis",
        "subsection": "Qualidades da prece",
        "item_number": "1",
        "subchunk_index": 1,
        "total_subchunks": 1,
        "content": "Sobre a qualidade da prece.",
        "footnotes": [],
    },
    {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO XXVII",
        "chapter_title": "Pedi e obtereis",
        "subsection": "Eficácia da prece",
        "item_number": "5",
        "subchunk_index": 1,
        "total_subchunks": 1,
        "content": "Sobre a eficácia da prece.",
        "footnotes": [],
    },
]


def test_returns_none_when_no_chunks(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", [])
    result = get_daily_passage()
    assert result is None


def test_returns_none_when_markdown_file_missing(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", None)
    monkeypatch.setattr(
        "src.rag.evangelho.TRECHO_DIARIO_PATH",
        "data/markdown_files/__does_not_exist__.md",
    )
    result = get_daily_passage()
    assert result is None


def test_returns_passage_with_correct_shape(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    result = get_daily_passage()
    assert result is not None
    assert "date" in result
    assert "content" in result
    assert "source" in result


def test_content_comes_from_selected_chunk(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    result = get_daily_passage()
    assert result["content"] == "Bem-aventurados os puros de coração."


def test_full_item_text_joins_all_subchunks_in_order():
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, datetime.date(2026, 8, 2))
    assert result["content"] == "Parte A Parte B Parte C"


def test_source_fields_populated_from_item_metadata(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    result = get_daily_passage()
    assert result["source"]["book"] == "O Evangelho Segundo o Espiritismo"
    assert result["source"]["chapter"] == "CAPÍTULO I"
    assert result["source"]["chapter_title"] == "Bem-aventuranças"
    assert result["source"]["item_number"] == "section-4"


def test_source_total_subchunks_reflects_real_split_count():
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, datetime.date(2026, 8, 2))
    assert result["source"]["total_subchunks"] == 3


def test_source_omits_subchunk_index():
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, datetime.date(2026, 8, 2))
    assert "subchunk_index" not in result["source"]


def test_same_date_returns_same_passage(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _TWO_ITEMS_TWO_CHAPTERS)
    result1 = get_daily_passage()
    result2 = get_daily_passage()
    assert result1["content"] == result2["content"]


def test_date_field_is_today_isoformat(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    result = get_daily_passage()
    assert result["date"] == datetime.date.today().isoformat()


def test_items_across_subsections_grouped_under_same_chapter():
    seen_items = set()
    for seed in range(20):
        result = _select_passage(
            _TWO_SUBSECTIONS_SAME_CHAPTER, datetime.date.fromordinal(739_000 + seed)
        )
        seen_items.add(result["source"]["item_number"])
    assert seen_items == {"1", "5"}


def test_chapter_summary_is_none_when_file_missing(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    monkeypatch.setattr("src.rag.evangelho._summaries", None)
    monkeypatch.setattr(
        "src.rag.evangelho.CHAPTER_SUMMARIES_PATH",
        "data/chapter_summaries/__does_not_exist__.json",
    )
    result = get_daily_passage()
    assert result["chapter_summary"] is None


def test_chapter_summary_is_populated_when_present(monkeypatch, tmp_path):
    summaries_file = tmp_path / "evangelho.json"
    summaries_file.write_text(
        '{"Bem-aventuranças": "Resumo do capítulo."}', encoding="utf-8"
    )
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    monkeypatch.setattr("src.rag.evangelho._summaries", None)
    monkeypatch.setattr("src.rag.evangelho.CHAPTER_SUMMARIES_PATH", str(summaries_file))
    result = get_daily_passage()
    assert result["chapter_summary"] == "Resumo do capítulo."


def test_chapter_summary_is_none_when_chapter_not_in_summaries(monkeypatch, tmp_path):
    summaries_file = tmp_path / "evangelho.json"
    summaries_file.write_text('{"Outro Capítulo": "..."}', encoding="utf-8")
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    monkeypatch.setattr("src.rag.evangelho._summaries", None)
    monkeypatch.setattr("src.rag.evangelho.CHAPTER_SUMMARIES_PATH", str(summaries_file))
    result = get_daily_passage()
    assert result["chapter_summary"] is None


# --- The daily rotation ---------------------------------------------------
#
# Picking a chapter at random and then an item inside it made the odds depend
# on chapter size: five chapters of trecho_diario.md hold a single item, so
# those items came up ten times more often than items in the ten-item chapter.
# Simulated over a year (2026-08-02): 268 of 365 days repeated a passage, the
# two most frequent appeared 18 times each, and 12 of the 109 curated passages
# were never served at all.
#
# Uniform choice does not fix it — 109 passages over 365 draws still collide on
# ~71% of days. Only drawing WITHOUT replacement does: the cycle walks every
# passage once before any repeats.


def _rotation(chunks, days, start=739_000):
    return [
        _select_passage(chunks, datetime.date.fromordinal(start + i))["content"]
        for i in range(days)
    ]


def test_a_date_always_yields_the_same_passage():
    day = datetime.date(2026, 8, 2)
    a = _select_passage(_TWO_ITEMS_TWO_CHAPTERS, day)
    b = _select_passage(_TWO_ITEMS_TWO_CHAPTERS, day)
    assert a["content"] == b["content"]


def test_no_passage_repeats_before_every_other_has_been_shown():
    n = len(_TWO_ITEMS_TWO_CHAPTERS)
    served = _rotation(_TWO_ITEMS_TWO_CHAPTERS, n)
    assert len(set(served)) == n


def test_every_passage_appears_exactly_once_per_cycle():
    n = len(_TWO_ITEMS_TWO_CHAPTERS)
    served = _rotation(_TWO_ITEMS_TWO_CHAPTERS, n * 3)
    for cycle in range(3):
        window = served[cycle * n : (cycle + 1) * n]
        assert sorted(window) == sorted(set(window)), "repeat inside one cycle"
        assert len(set(window)) == n


def test_a_single_item_corpus_still_works():
    served = _rotation(_SINGLE_CHUNK, 3)
    assert served == [_SINGLE_CHUNK[0]["content"]] * 3


def test_chapter_size_no_longer_decides_the_odds():
    """A chapter holding one item and a chapter holding three: over one cycle
    each ITEM is served once, so the lone item is not favoured."""
    corpus = _TWO_ITEMS_TWO_CHAPTERS + [
        {
            **_TWO_ITEMS_TWO_CHAPTERS[1],
            "item_number": f"section-{n}",
            "content": f"Extra {n}",
        }
        for n in (8, 9)
    ]
    served = _rotation(corpus, len(corpus))
    assert len(set(served)) == len(corpus)


def test_a_passage_does_not_come_back_across_a_cycle_boundary():
    """Independent reshuffles let a passage close one cycle and open the next,
    which a daily reader sees as the same text twice in one week — the very
    thing the rotation exists to prevent. Measured with per-cycle reshuffling:
    a 3-day gap. With one fixed order the spacing is a full cycle, always."""
    corpus = [
        {**_SINGLE_CHUNK[0], "item_number": f"section-{n}", "content": f"Trecho {n}"}
        for n in range(40)
    ]
    n = len(corpus)
    # Several windows: a boundary collision depends on where the calendar falls
    # against the cycle, so one window can pass by luck.
    worst = n
    for offset in range(0, 400, 7):
        served = _rotation(corpus, n * 4, start=739_000 + offset)
        last: dict[str, int] = {}
        for i, text in enumerate(served):
            if text in last:
                worst = min(worst, i - last[text])
            last[text] = i
    assert worst >= 7, f"came back after only {worst} days"
