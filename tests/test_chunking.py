from src.parsing.chunking import split_into_subchunks


def test_oversized_single_paragraph_is_split_under_max_chars():
    paragraph = "Frase. " * 100  # single "line" (no \n), 700 chars, no split points a naive approach would use
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
