from src.rag.markers import parse_sections, split_pipe_list, strip_trailing_markers


def _chunks(n):
    return [
        {"metadata": {"item_number": str(i)}, "content": f"c{i}"}
        for i in range(1, n + 1)
    ]


# --- parse_sections ---------------------------------------------------------


def test_parses_flat_sections():
    text = "CONTEXTO: primeiro trecho.\nCONCEITOS: a | b"
    out = parse_sections(text, ["CONTEXTO", "CONCEITOS"])
    assert out["CONTEXTO"] == "primeiro trecho."
    assert out["CONCEITOS"] == "a | b"


def test_section_body_spans_multiple_lines_until_next_marker():
    text = "ACOLHIMENTO: linha um.\nlinha dois.\nCONEXAO: doutrina."
    out = parse_sections(text, ["ACOLHIMENTO", "CONEXAO"])
    assert out["ACOLHIMENTO"] == "linha um.\nlinha dois."
    assert out["CONEXAO"] == "doutrina."


def test_missing_section_is_empty_string():
    out = parse_sections("CONTEXTO: só isso.", ["CONTEXTO", "CONCEITOS"])
    assert out["CONCEITOS"] == ""


def test_tolerates_brackets_and_stray_slash():
    text = "[CONTEXTO]: um.\n/CONCEITOS: a | b"
    out = parse_sections(text, ["CONTEXTO", "CONCEITOS"])
    assert out["CONTEXTO"] == "um."
    assert out["CONCEITOS"] == "a | b"


def test_lowercase_prose_is_not_a_marker():
    """Ordinary prose must never be swallowed as a section."""
    text = "CONTEXTO: falamos sobre as fontes: a caridade e a fé."
    out = parse_sections(text, ["CONTEXTO", "FONTES"])
    assert out["CONTEXTO"] == "falamos sobre as fontes: a caridade e a fé."
    assert out["FONTES"] == ""


def test_returns_empty_for_unmarked_text():
    out = parse_sections("um texto sem marcadores nenhum", ["CONTEXTO"])
    assert out["CONTEXTO"] == ""


def test_title_case_labels_are_accepted():
    """The model writes "Acolhimento:" as readily as "ACOLHIMENTO:"."""
    text = "Acolhimento: sinto muito.\nConexao: a doutrina consola."
    out = parse_sections(text, ["ACOLHIMENTO", "CONEXAO"])
    assert out["ACOLHIMENTO"] == "sinto muito."
    assert out["CONEXAO"] == "a doutrina consola."


# --- split_pipe_list --------------------------------------------------------


def test_splits_and_trims():
    assert split_pipe_list(" a | b |  c ") == ["a", "b", "c"]


def test_drops_empties_and_applies_limit():
    assert split_pipe_list("a || b | c", limit=2) == ["a", "b"]


def test_empty_body_gives_empty_list():
    assert split_pipe_list("") == []


# --- strip_trailing_markers (moved, behavior must be identical) -------------


def test_strips_both_markers_and_filters_sources():
    answer, chunks, sugg = strip_trailing_markers(
        "Resposta.\n[FONTES: 1, 3]\n[SEGUIR: q1 | q2]", _chunks(3)
    )
    assert answer == "Resposta."
    assert [c["content"] for c in chunks] == ["c1", "c3"]
    assert sugg == ["q1", "q2"]


def test_empty_fontes_means_no_sources():
    _, chunks, _ = strip_trailing_markers("Resposta.\n[FONTES:]", _chunks(3))
    assert chunks == []


def test_missing_markers_keep_all_chunks():
    answer, chunks, sugg = strip_trailing_markers("Resposta.", _chunks(2))
    assert answer == "Resposta."
    assert len(chunks) == 2
    assert sugg == []


def test_tolerates_malformed_marker():
    answer, _, _ = strip_trailing_markers("Resposta.\n/FONTES: 1", _chunks(2))
    assert answer == "Resposta."
