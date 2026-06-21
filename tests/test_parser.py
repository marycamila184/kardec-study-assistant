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
