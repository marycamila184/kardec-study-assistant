import pytest

from src.parsing.parser import parse_md_to_json

CEU_INFERNO = "O Céu e o Inferno"
EVANGELHO = "O Evangelho Segundo o Espiritismo"


def test_numbered_items_without_dash_are_parsed():
    """Items like '1. text' (no dash) must be detected as item boundaries."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Primeiro parágrafo do capítulo.
2. Segundo parágrafo do capítulo.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    numbers = [c["item_number"] for c in chunks]
    assert "1" in numbers
    assert "2" in numbers


def test_part_heading_sets_part_metadata():
    md = """\
# I PARTE

# CAPÍTULO 1

# O TÍTULO

1. Conteúdo do item.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert len(chunks) > 0
    assert all(c["part"] == "I PARTE" for c in chunks)


def test_chapter_title_not_overwritten_by_subsection_heading():
    """Headings after the chapter title must not overwrite chapter_title."""
    md = """\
# CAPÍTULO I

# O PORVIR E O NADA

1. Item antes da subseção.

# Uma subseção interna

2. Item dentro da subseção.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert len(chunks) == 2
    assert all(c["chapter_title"] == "O PORVIR E O NADA" for c in chunks)


def test_subsection_field_set_after_chapter_title():
    """First heading after CAPÍTULO → chapter_title; subsequent → subsection."""
    md = """\
# CAPÍTULO I

# O PORVIR E O NADA

1. Item antes da subseção.

# Uma subseção interna

2. Item dentro da subseção.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    item1 = next(c for c in chunks if c["item_number"] == "1")
    item2 = next(c for c in chunks if c["item_number"] == "2")
    assert item1["subsection"] is None
    assert item2["subsection"] == "Uma subseção interna"


def test_new_chapter_resets_chapter_title_and_subsection():
    md = """\
# CAPÍTULO I

# TÍTULO UM

1. Item do primeiro capítulo.

# CAPÍTULO II

# TÍTULO DOIS

1. Item do segundo capítulo.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    ch1 = next(c for c in chunks if c["chapter"] == "CAPÍTULO I")
    ch2 = next(c for c in chunks if c["chapter"] == "CAPÍTULO II")
    assert ch1["chapter_title"] == "TÍTULO UM"
    assert ch2["chapter_title"] == "TÍTULO DOIS"
    assert ch2["subsection"] is None


def test_ceu_inferno_doutrina_heading_not_carried_into_chapter():
    """'# DOUTRINA' before any CAPÍTULO must not bleed into the chapter title."""
    md = """\
# I PARTE

# DOUTRINA

# CAPÍTULO 1

# O PORVIR E O NADA

1. Conteúdo.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert chunks[0]["chapter_title"] == "O PORVIR E O NADA"
    assert chunks[0]["part"] == "I PARTE"


def test_evangelho_instruções_dos_espíritos_is_subsection_not_chapter_title():
    """INSTRUÇÕES DOS ESPÍRITOS heading must set subsection, not chapter_title."""
    md = """\
# CAPÍTULO I

# NÃO VIM DESTRUIR A LEI

1. Primeiro item.

# INSTRUÇÕES DOS ESPÍRITOS

# A nova era

9. Nono item.
"""
    chunks = parse_md_to_json(md, EVANGELHO)
    item1 = next(c for c in chunks if c["item_number"] == "1")
    item9 = next(c for c in chunks if c["item_number"] == "9")
    assert item1["chapter_title"] == "NÃO VIM DESTRUIR A LEI"
    assert item1["subsection"] is None
    assert item9["chapter_title"] == "NÃO VIM DESTRUIR A LEI"
    assert item9["subsection"] == "A nova era"


def test_evangelho_chapter_subtitle_toc_heading_not_overwriting_chapter_title():
    """The TOC-like heading after chapter title must become subsection, not chapter_title."""
    md = """\
# CAPÍTULO I

# NÃO VIM DESTRUIR A LEI

# As três revelações: Moisés, Cristo, Espiritismo.

1. Não penseis que eu tenha vindo destruir a lei.
"""
    chunks = parse_md_to_json(md, EVANGELHO)
    assert chunks[0]["chapter_title"] == "NÃO VIM DESTRUIR A LEI"


def test_subsection_field_present_in_all_chunks():
    """Every chunk must include a 'subsection' key."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Conteúdo.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert all("subsection" in c for c in chunks)


# ── Footnote tests ────────────────────────────────────────────────────────────

def test_paragraph_footnote_attached_only_to_its_chunk():
    """A footnote following a paragraph must appear in that chunk's footnotes only."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Primeiro parágrafo. (1)

__________

(1) Nota do primeiro parágrafo.

__________

2. Segundo parágrafo.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    item1 = next(c for c in chunks if c["item_number"] == "1")
    item2 = next(c for c in chunks if c["item_number"] == "2")
    assert item1["footnotes"] == [{"number": "1", "content": "Nota do primeiro parágrafo."}]
    assert item2["footnotes"] == []


def test_title_footnote_stored_in_title_footnotes_not_content_footnotes():
    """A footnote immediately after a heading must go into title_footnotes, not footnotes."""
    md = """\
# CAPÍTULO I

# O TÍTULO (1)

__________

(1) Nota explicativa do título.

__________

1. Conteúdo do item.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert len(chunks) == 1
    assert chunks[0]["title_footnotes"] == [{"number": "1", "content": "Nota explicativa do título."}]
    assert chunks[0]["footnotes"] == []


def test_multiple_footnotes_in_one_block_all_attached_to_same_chunk():
    """Two footnotes in one ___…___ block must both be on the same paragraph chunk."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Parágrafo com duas notas. (1) e (2)

__________

(1) Primeira nota.

(2) Segunda nota.

__________

2. Próximo item.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    item1 = next(c for c in chunks if c["item_number"] == "1")
    assert {"number": "1", "content": "Primeira nota."} in item1["footnotes"]
    assert {"number": "2", "content": "Segunda nota."} in item1["footnotes"]


def test_two_inline_footnote_blocks_within_one_item():
    """Two separate footnote blocks inside one numbered item produce independent chunks."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Parágrafo A. (1)

__________

(1) Nota A.

__________

Parágrafo B. (2)

__________

(2) Nota B.

__________

2. Próximo item.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    item1_chunks = [c for c in chunks if c["item_number"] == "1"]
    assert len(item1_chunks) == 2
    footnotes_by_chunk = [c["footnotes"] for c in item1_chunks]
    assert [{"number": "1", "content": "Nota A."}] in footnotes_by_chunk
    assert [{"number": "2", "content": "Nota B."}] in footnotes_by_chunk


def test_title_footnotes_carried_into_all_chunks_under_that_title():
    """title_footnotes must appear on every chunk that lives under the footnoted title."""
    md = """\
# CAPÍTULO I

# O TÍTULO (1)

__________

(1) Nota do título.

__________

1. Primeiro item.

2. Segundo item.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert len(chunks) == 2
    expected = [{"number": "1", "content": "Nota do título."}]
    assert all(c["title_footnotes"] == expected for c in chunks)


def test_footnote_on_subsection_stored_in_title_footnotes():
    """A footnote after a subsection heading must go into title_footnotes."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Item antes da subseção.

# Uma subseção (1)

__________

(1) Nota da subseção.

__________

2. Item dentro da subseção.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    item2 = next(c for c in chunks if c["item_number"] == "2")
    assert item2["title_footnotes"] == [{"number": "1", "content": "Nota da subseção."}]
    assert item2["footnotes"] == []


def test_chunk_without_footnote_has_empty_lists():
    """Chunks with no footnotes must have footnotes=[] and title_footnotes=[]."""
    md = """\
# CAPÍTULO I

# O TÍTULO

1. Conteúdo simples.
"""
    chunks = parse_md_to_json(md, CEU_INFERNO)
    assert chunks[0]["footnotes"] == []
    assert chunks[0]["title_footnotes"] == []
