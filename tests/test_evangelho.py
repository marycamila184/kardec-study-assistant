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
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, seed="fixed-seed")
    assert result["content"] == "Parte A Parte B Parte C"


def test_source_fields_populated_from_item_metadata(monkeypatch):
    monkeypatch.setattr("src.rag.evangelho._chunks", _SINGLE_CHUNK)
    result = get_daily_passage()
    assert result["source"]["book"] == "O Evangelho Segundo o Espiritismo"
    assert result["source"]["chapter"] == "CAPÍTULO I"
    assert result["source"]["chapter_title"] == "Bem-aventuranças"
    assert result["source"]["item_number"] == "section-4"


def test_source_total_subchunks_reflects_real_split_count():
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, seed="fixed-seed")
    assert result["source"]["total_subchunks"] == 3


def test_source_omits_subchunk_index():
    result = _select_passage(_MULTI_SUBCHUNK_ITEM, seed="fixed-seed")
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
        result = _select_passage(_TWO_SUBSECTIONS_SAME_CHAPTER, seed=str(seed))
        seen_items.add(result["source"]["item_number"])
    assert seen_items == {"1", "5"}
