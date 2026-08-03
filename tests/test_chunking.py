from src.parsing.chunking import (
    join_subchunks,
    split_into_subchunks,
    split_with_paragraph_breaks,
)


def test_oversized_single_paragraph_is_split_under_max_chars():
    paragraph = (
        "Frase. " * 100
    )  # single "line" (no \n), 700 chars, no split points a naive approach would use
    chunks = split_into_subchunks(paragraph, max_chars=400)
    assert all(len(c) <= 400 for c in chunks)
    assert len(chunks) > 1


def test_oversized_paragraph_split_preserves_all_words():
    paragraph = "Frase. " * 100
    chunks = split_into_subchunks(paragraph, max_chars=400)
    assert " ".join(chunks).split() == paragraph.split()


def test_oversized_paragraph_without_sentence_boundaries_splits_on_words():
    paragraph = "palavra " * 100  # 800 chars, single "sentence", no ./!/?/;
    chunks = split_into_subchunks(paragraph, max_chars=400)
    assert all(len(c) <= 400 for c in chunks)
    assert len(chunks) > 1


def test_short_paragraphs_still_merge_into_one_subchunk():
    text = "Primeira linha.\nSegunda linha.\nTerceira linha."
    chunks = split_into_subchunks(text, max_chars=400)
    assert len(chunks) == 1
    assert "Primeira linha." in chunks[0]
    assert "Terceira linha." in chunks[0]


def test_paragraph_exactly_at_max_chars_does_not_emit_empty_leading_chunk():
    # A single paragraph whose length exactly equals max_chars used to hit
    # the flush branch with an empty buffer, emitting a spurious "" chunk
    # before the real content.
    paragraph = "a" * 400
    chunks = split_into_subchunks(paragraph, max_chars=400)
    assert "" not in chunks
    assert chunks == [paragraph]


def test_paragraph_at_max_chars_after_nonempty_buffer_does_not_lose_buffer():
    text = "Curta.\n" + ("b" * 400)
    chunks = split_into_subchunks(text, max_chars=400)
    assert "" not in chunks
    assert chunks[0] == "Curta."
    assert chunks[1] == "b" * 400


# --- Abbreviations are not sentence ends ---------------------------------
#
# A period is only a sentence boundary when the token it closes is a word.
# The measured exceptions in this corpus (2026-08-02, counts over all five
# works): citation abbreviations `cap.` (442), `vv.` (291), `pág.` (95),
# `Art.` (30); and single letters — `S.` for São (382), and `R.`/`P.` (557),
# the Resposta/Pergunta markers that open every line of the Céu e o Inferno
# dialogues. Cutting after one of these strands the marker from what it marks.


def test_citation_abbreviation_does_not_end_a_sentence():
    text = ("a " * 200) + "fim do trecho. (S. MARCOS, cap. Xl, vv. 12 a 14 e 20 a 23.)"
    chunks = split_into_subchunks(text, max_chars=420)
    assert not any(c.endswith("cap.") for c in chunks)
    assert not any(c.endswith("(S.") for c in chunks)
    assert not any(c.startswith("Xl,") for c in chunks)


def test_dialogue_markers_stay_attached_to_their_line():
    # O Céu e o Inferno evocations: "P." asks, "R." answers.
    text = ("palavra " * 60) + "fim da pergunta? R. A minha situação é bem ditosa."
    chunks = split_into_subchunks(text, max_chars=300)
    assert not any(c.endswith("R.") for c in chunks)


def test_initials_do_not_end_a_sentence():
    # Real sentence ends exist here, so the sentence path is what chooses the
    # cut — the guarantee is about that path. The word fallback, used only for
    # a run with no true boundary at all, can still land anywhere by design.
    text = ("Uma frase qualquer. " * 20) + "Conforme escreveu A. Kardec na obra."
    chunks = split_into_subchunks(text, max_chars=210)
    assert not any(c.endswith("A.") for c in chunks)


def test_real_sentence_ends_still_split():
    text = "Primeira frase completa. " * 40
    chunks = split_into_subchunks(text, max_chars=300)
    assert len(chunks) > 1
    assert all(c.rstrip().endswith(".") for c in chunks)


def test_abbreviations_never_break_the_max_chars_guarantee():
    # Suppressing a boundary must not let a piece grow past the cap: the word
    # fallback still has to catch it.
    text = ("cap. " * 300).strip()
    chunks = split_into_subchunks(text, max_chars=200)
    assert all(len(c) <= 200 for c in chunks)


def test_abbreviation_rule_loses_no_text():
    text = ("palavra " * 100) + "vede o cap. XII, vv. 3 a 9, e a pág. 44 do Sr. Kardec."
    chunks = split_into_subchunks(text, max_chars=250)
    assert " ".join(chunks).split() == text.split()


# --- Reassembly ---------------------------------------------------------
#
# Subchunking exists for embedding, but the reader is shown the item whole:
# /study and free study both put the pieces back together. That only works if
# the split records where it cut. A paragraph the parser stored as ONE line
# must come back as one line — the separator that reassembly invents is what
# the reader sees, because "Da Obra" renders with white-space: pre-wrap.


def test_split_reports_first_subchunk_as_paragraph_start():
    pieces = split_with_paragraph_breaks("Curta.", max_chars=400)
    assert pieces == [("Curta.", True)]


def test_oversized_paragraph_pieces_do_not_start_a_paragraph():
    paragraph = "Frase. " * 100
    pieces = split_with_paragraph_breaks(paragraph, max_chars=400)
    assert len(pieces) > 1
    assert pieces[0][1] is True
    assert all(starts is False for _, starts in pieces[1:])


def test_separate_paragraphs_each_start_a_paragraph():
    text = ("a" * 300) + "\n" + ("b" * 300)
    pieces = split_with_paragraph_breaks(text, max_chars=400)
    assert [starts for _, starts in pieces] == [True, True]


def test_join_restores_a_single_oversized_paragraph_verbatim():
    paragraph = "Frase número um. " * 60
    paragraph = paragraph.strip()
    assert join_subchunks(split_with_paragraph_breaks(paragraph, 400)) == paragraph


def test_join_restores_paragraph_structure():
    text = ("a" * 300) + "\n" + ("b" * 300)
    assert join_subchunks(split_with_paragraph_breaks(text, 400)) == text


def test_join_restores_mixed_short_and_oversized_paragraphs():
    text = "Curta.\n" + ("Frase longa. " * 60).strip() + "\nOutra curta."
    assert join_subchunks(split_with_paragraph_breaks(text, 400)) == text


def test_join_never_invents_a_blank_line():
    # The bug: reassembly used "\n\n", a separator the source never had, and
    # pre-wrap turned it into a blank line in the middle of a citation
    # ("(S. MARCOS, cap." / "Xl, vv. 12 a 14 e 20 a 23.)").
    text = ("Palavra. " * 200).strip()
    assert "\n\n" not in join_subchunks(split_with_paragraph_breaks(text, 400))
