from src.rag.citations import (
    extract_model_citations,
    retrieved_ids,
    strip_model_citations,
    validate_model_citations,
)


def _chunk(book, item):
    return {"metadata": {"book": book, "item_number": item}, "content": "x"}


# --- extraction -------------------------------------------------------------


def test_extracts_sigla_form():
    assert extract_model_citations("conforme LE-625 e LM 132") == {"LE-625", "LM-132"}


def test_extracts_prose_form_with_book_name():
    text = "como diz a questão 625 do Livro dos Espíritos"
    assert extract_model_citations(text) == {"LE-625"}


def test_extracts_accentless_prose_form():
    assert extract_model_citations("a questao 625 do Livro dos Espiritos") == {"LE-625"}


def test_no_citation_returns_empty_set():
    assert extract_model_citations("uma resposta sem citação alguma") == set()


def test_bare_number_is_not_a_citation():
    """A number with no book context must not be read as a citation."""
    assert extract_model_citations("havia 625 pessoas") == set()


def test_prose_number_does_not_borrow_book_from_next_sentence():
    """The 60-char lookahead must not cross a sentence boundary to grab a
    book name that belongs to an unrelated clause."""
    text = (
        "Reunimos a questão 42 do capítulo anterior. "
        "Kardec, autor do Livro dos Espíritos, viveu no século XIX."
    )
    assert extract_model_citations(text) == set()


# --- retrieved ids ----------------------------------------------------------


def test_builds_ids_from_chunk_metadata():
    chunks = [_chunk("O Livro dos Espíritos", "625"), _chunk("A Gênese", "12")]
    assert retrieved_ids(chunks) == {"LE-625", "GE-12"}


def test_skips_placeholder_item_numbers():
    """The parser's 'section-N' placeholders are not citable references."""
    assert retrieved_ids([_chunk("O Livro dos Espíritos", "section-3")]) == set()


# --- validation -------------------------------------------------------------


def test_all_cited_ids_retrieved_is_trustworthy():
    out = validate_model_citations({"LE-625"}, {"LE-625", "LE-626"})
    assert out == {"exibir": ["LE-625"], "alucinadas": [], "confiavel": True}


def test_citation_outside_retrieved_set_is_flagged():
    out = validate_model_citations({"LE-625", "LE-999"}, {"LE-625"})
    assert out["exibir"] == ["LE-625"]
    assert out["alucinadas"] == ["LE-999"]
    assert out["confiavel"] is False


def test_no_citations_is_trustworthy():
    out = validate_model_citations(set(), {"LE-625"})
    assert out["confiavel"] is True


# --- stripping --------------------------------------------------------------


def test_strips_parenthetical_citation():
    text = "A caridade é o essencial (O Livro dos Espíritos, questão 886)."
    assert strip_model_citations(text) == "A caridade é o essencial."


def test_leaves_parenthetical_that_merely_mentions_a_book():
    """A parenthetical that names a work but has no citation shape (no
    number, no questão/item/capítulo word) is clarifying prose, not a
    citation, and must not be stripped."""
    text = "Kardec organizou a obra (o Livro dos Espíritos foi o primeiro) com base nas respostas."
    assert strip_model_citations(text) == text


def test_strips_sigla_reference():
    assert strip_model_citations("Conforme LE-625, a alma persiste.") == (
        "Conforme, a alma persiste."
    )


def test_leaves_clean_text_untouched():
    text = "A caridade é o essencial da doutrina."
    assert strip_model_citations(text) == text


def test_strips_the_models_own_source_line():
    """Observed verbatim in the smoke test — including invented question
    numbers for passages supplied with no numbers at all."""
    text = (
        "A caridade é a benevolência para com todos.\n\n"
        "📖 Fonte: O Livro dos Espíritos, questões 887-889."
    )
    assert strip_model_citations(text) == "A caridade é a benevolência para com todos."


def test_strips_source_line_without_emoji():
    text = "A alma persiste.\nFonte: O Livro dos Espíritos, Capítulo I."
    assert strip_model_citations(text) == "A alma persiste."


def test_leaves_source_line_that_names_no_work():
    """A line starting with 'Fonte:' that does not name one of the five
    canonical works is legitimate prose, not a model citation trailer."""
    text = (
        "A fonte principal é a razão.\n"
        "Fonte: inspiração divina, segundo os espíritos superiores."
    )
    assert strip_model_citations(text) == text
