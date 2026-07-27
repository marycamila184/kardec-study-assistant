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


def test_prose_ref_not_truncated_by_abbreviation_period():
    """An abbreviation like 'cap.' must not be mistaken for a sentence
    boundary, or the book name after it is lost."""
    text = "questão 625 cap. II do Livro dos Espíritos"
    assert extract_model_citations(text) == {"LE-625"}


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


def test_strips_book_only_parenthetical_citation():
    """A parenthetical naming a work with no locator number is still a
    citation and must be stripped, not merely a mention in passing."""
    text = "A doutrina se apoia (O Livro dos Espíritos) nas respostas dos espíritos."
    assert (
        strip_model_citations(text)
        == "A doutrina se apoia nas respostas dos espíritos."
    )


def test_strips_book_only_source_line():
    """A 'Fonte:' line naming a work with no question number is still a
    model citation trailer and must be stripped whole."""
    text = "A alma persiste.\nFonte: O Evangelho Segundo o Espiritismo."
    assert strip_model_citations(text) == "A alma persiste."


# --- unified predicate: new coverage --------------------------------------


def test_strips_parenthetical_with_question_range():
    text = "A caridade é central (O Livro dos Espíritos, questões 887-889)."
    assert strip_model_citations(text) == "A caridade é central."


def test_strips_parenthetical_with_capitulo_abbreviation():
    text = "A doutrina (O Livro dos Espíritos, cap. IV) trata disso."
    assert strip_model_citations(text) == "A doutrina trata disso."


def test_strips_parenthetical_with_multiple_locators():
    text = "A questão trata da alma (O Livro dos Espíritos, questão 625, cap. II)."
    assert strip_model_citations(text) == "A questão trata da alma."


def test_strips_book_only_parenthetical_no_locator_duplicate_shape():
    text = "A doutrina se apoia (O Livro dos Espíritos) nas respostas dos espíritos."
    assert (
        strip_model_citations(text)
        == "A doutrina se apoia nas respostas dos espíritos."
    )


def test_strips_source_line_with_question_range_and_emoji():
    text = "A alma persiste.\n📖 Fonte: O Livro dos Espíritos, questões 887-889."
    assert strip_model_citations(text) == "A alma persiste."


def test_strips_sigla_ref_conforme():
    assert strip_model_citations("Conforme LE-625, a alma persiste.") == (
        "Conforme, a alma persiste."
    )


def test_leaves_parenthetical_that_is_pure_mention_not_citation_shape():
    text = "Kardec organizou a obra (o Livro dos Espíritos foi o primeiro) com base nas respostas."
    assert strip_model_citations(text) == text


def test_leaves_parenthetical_with_locator_words_but_no_book():
    """A parenthetical with locator-shaped words but no book name is not a
    citation — book presence is required by the unified predicate."""
    text = "Isso é claro (questão 42, item 3)."
    assert strip_model_citations(text) == text


def test_extracts_plural_questoes_range_from_prose():
    result = extract_model_citations(
        "conforme as questões 887-889 do Livro dos Espíritos"
    )
    assert result
    assert result in ({"LE-887", "LE-888", "LE-889"}, {"LE-887"})


# --- order-agnostic shape predicate (locator-first citations) --------------


def test_strips_parenthetical_with_locator_before_book():
    """The model may write the locator before the book name — the shape
    predicate must strip this order too, not just 'book then locator'."""
    text = "A caridade é central (questão 625 do Livro dos Espíritos)."
    assert strip_model_citations(text) == "A caridade é central."


def test_strips_source_line_with_locator_before_book():
    text = "A alma persiste.\nFonte: questão 625 do Livro dos Espíritos."
    assert strip_model_citations(text) == "A alma persiste."


# --- attribution checks ------------------------------------------------------


def test_books_mentioned_finds_each_work_by_any_spelling():
    from src.rag.citations import books_mentioned

    assert books_mentioned("ver O Livro dos Espiritos e a Genese") == {"LE", "GE"}
    assert books_mentioned("nada aqui") == set()


def test_unsupplied_books_flags_a_work_never_given_to_the_model():
    from src.rag.citations import unsupplied_books

    text = "Como mostra O Livro dos Médiuns, a mediunidade é uma aptidão."
    assert unsupplied_books(text, ["O Livro dos Espíritos"]) == {"LM"}
    assert unsupplied_books(text, ["O Livro dos Médiuns"]) == set()


def test_misattribution_catches_the_observed_riv_ai_error():
    """Verbatim shape of the 2026-07-25 failure: LE 886 attributed to ESE."""
    from src.rag.citations import misattributions

    text = 'O trecho é extraído da obra "O Evangelho Segundo o Espiritismo".'
    assert misattributions(text, "O Livro dos Espíritos")
    assert misattributions(text, "O Evangelho Segundo o Espiritismo") == []

    # Also from the 2026-07-25 run, on the 70B this time: O Livro dos Médiuns
    # 132 declared to be part of O Livro dos Espíritos.
    real = "A passagem é parte do Livro dos Espíritos, de Allan Kardec."
    assert misattributions(real, "O Livro dos Médiuns")
    assert misattributions(real, "O Livro dos Espíritos") == []


def test_misattribution_ignores_a_passing_mention_of_another_work():
    """Naming another work to draw a connection is legitimate and required —
    only an explicit attribution OF THE MAIN PASSAGE is an error."""
    from src.rag.citations import misattributions

    for text in [
        "A mesma ideia reaparece em O Livro dos Médiuns.",
        "Kardec retoma esse ponto na Gênese, ao tratar dos milagres.",
        "Esta passagem dialoga com O Céu e o Inferno.",
        # From the 2026-07-25 run: a cross-reference the first version of the
        # regex flagged as misattribution. A reference is not a claim about
        # where the passage under study came from.
        "conforme o Item 14 do Evangelho Segundo o Espiritismo",
        "ver a questão 625 do Livro dos Espíritos sobre o mesmo tema",
    ]:
        assert misattributions(text, "O Livro dos Espíritos") == [], text


def test_misattribution_empty_when_nothing_is_named():
    from src.rag.citations import misattributions

    assert misattributions("O texto trata da caridade.", "O Livro dos Espíritos") == []
