from src.rag.mode_detector import detect_suggested_mode, extract_study_reference


def test_detects_questao_with_number():
    assert detect_suggested_mode("o que é questão 132?") == "estudar_obra"


def test_detects_questao_without_accent():
    assert (
        detect_suggested_mode("explique a questao 132 do livro dos espiritos")
        == "estudar_obra"
    )


def test_extract_study_reference_without_accents():
    ref = extract_study_reference("explique a questao 132 do livro dos espiritos")
    assert ref["item_number"] == "132"
    assert ref["book"] == "O Livro dos Espíritos"


def test_detects_item_with_number():
    assert detect_suggested_mode("explique o item 45") == "estudar_obra"


def test_detects_q_dot_with_number():
    assert detect_suggested_mode("qual o significado de Q. 76?") == "estudar_obra"


def test_detects_explique_a_questao():
    assert detect_suggested_mode("explique a questão sobre espíritos") == "estudar_obra"


def test_detects_o_que_diz_with_number():
    assert detect_suggested_mode("o que diz Kardec no item 200") == "estudar_obra"


def test_returns_none_for_generic_question():
    assert detect_suggested_mode("o que é reencarnação?") is None


def test_returns_none_for_empty_string():
    assert detect_suggested_mode("") is None


def test_detects_refletir_for_fear():
    assert detect_suggested_mode("tenho medo de morrer") == "refletir"


def test_detects_refletir_for_grief():
    assert detect_suggested_mode("perdi minha mãe e não sei lidar") == "refletir"


def test_detects_refletir_for_anxiety():
    assert detect_suggested_mode("estou com muita ansiedade ultimamente") == "refletir"


def test_estudar_wins_over_refletir_when_both_match():
    # situational word "medo" + explicit item lookup -> study intent wins
    assert detect_suggested_mode("tenho medo, explique a questão 132") == "estudar_obra"


def test_generic_question_still_returns_none():
    assert detect_suggested_mode("o que é reencarnação?") is None


def test_extract_study_reference_questao_defaults_to_livro_espiritos():
    # "questão N" with no book named implies O Livro dos Espíritos by convention
    ref = extract_study_reference("explique a questão 132")
    assert ref["item_number"] == "132"
    assert ref["book"] == "O Livro dos Espíritos"


def test_extract_study_reference_item_number_has_no_default_book():
    ref = extract_study_reference("o que significa o item 45?")
    assert ref["item_number"] == "45"
    assert ref["book"] is None


def test_extract_study_reference_q_dot():
    ref = extract_study_reference("qual o sentido de Q. 76?")
    assert ref["item_number"] == "76"
    assert ref["book"] == "O Livro dos Espíritos"


def test_extract_study_reference_named_book_beats_questao_default():
    ref = extract_study_reference("questão 5 do evangelho")
    assert ref["item_number"] == "5"
    assert ref["book"] == "O Evangelho Segundo o Espiritismo"


def test_extract_study_reference_with_book_livro_espiritos():
    ref = extract_study_reference("questão 132 do Livro dos Espíritos")
    assert ref["item_number"] == "132"
    assert ref["book"] == "O Livro dos Espíritos"


def test_extract_study_reference_with_book_evangelho():
    ref = extract_study_reference("o que diz o Evangelho no item 5?")
    assert ref["item_number"] == "5"
    assert ref["book"] == "O Evangelho Segundo o Espiritismo"


def test_extract_study_reference_with_book_ceu_e_inferno():
    ref = extract_study_reference("item 3 de O Céu e o Inferno")
    assert ref["book"] == "O Céu e o Inferno"


def test_extract_study_reference_without_number():
    ref = extract_study_reference("explique a questão sobre espíritos")
    assert ref["item_number"] is None
    assert ref["book"] is None


def test_extract_study_reference_o_que_diz_fallback():
    ref = extract_study_reference("o que diz Kardec no número 200")
    assert ref["item_number"] == "200"
