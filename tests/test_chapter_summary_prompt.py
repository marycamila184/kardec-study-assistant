from src.rag.chapter_summary_prompt import (
    build_chapter_summary_messages,
    clean_chapter_summary,
)


def test_build_messages_includes_chapter_title_and_text():
    system, messages = build_chapter_summary_messages(
        "NÃO VIM DESTRUIR A LEI", "Texto do capítulo aqui."
    )
    assert "NÃO VIM DESTRUIR A LEI" in system
    assert "Texto do capítulo aqui." in system
    assert messages == [
        {"role": "user", "content": "Resuma do que trata este capítulo."}
    ]


def test_build_messages_truncates_long_chapter_text():
    long_text = "a" * 10000
    system, _ = build_chapter_summary_messages("Título", long_text)
    assert "a" * 8001 not in system
    assert "a" * 8000 in system


def test_clean_chapter_summary_strips_whitespace():
    assert clean_chapter_summary("  resumo aqui.  \n") == "resumo aqui."


def test_clean_chapter_summary_strips_wrapping_quotes():
    assert clean_chapter_summary('"resumo aqui."') == "resumo aqui."


def test_clean_chapter_summary_strips_markdown_fence():
    assert clean_chapter_summary("```\nresumo aqui.\n```") == "resumo aqui."
