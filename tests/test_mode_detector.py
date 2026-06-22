from src.rag.mode_detector import detect_suggested_mode


def test_detects_questao_with_number():
    assert detect_suggested_mode("o que é questão 132?") == "estudar_obra"


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
