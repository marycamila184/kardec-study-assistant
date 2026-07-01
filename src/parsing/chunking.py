import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;])\s+")


def _split_oversized_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """
    Splits a single paragraph that already exceeds max_chars, preferring
    sentence boundaries and falling back to word boundaries.
    """
    pieces = []
    buffer = ""

    for sentence in _SENTENCE_BOUNDARY.split(paragraph):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if buffer:
                pieces.append(buffer.strip())
                buffer = ""
            word_buffer = ""
            for word in sentence.split(" "):
                candidate = f"{word_buffer} {word}".strip()
                if word_buffer and len(candidate) > max_chars:
                    pieces.append(word_buffer.strip())
                    word_buffer = word
                else:
                    word_buffer = candidate
            if word_buffer:
                pieces.append(word_buffer.strip())
        else:
            candidate = f"{buffer} {sentence}".strip()
            if buffer and len(candidate) > max_chars:
                pieces.append(buffer.strip())
                buffer = sentence
            else:
                buffer = candidate

    if buffer:
        pieces.append(buffer.strip())

    return pieces


def split_into_subchunks(text: str, max_chars: int = 800):
    """
    Splits long text into subchunks of at most max_chars, preserving
    paragraph structure and, for paragraphs too long on their own,
    sentence/word structure.
    """
    paragraphs = text.split("\n")
    subchunks = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if buffer.strip():
                subchunks.append(buffer.strip())
            buffer = ""
            subchunks.extend(_split_oversized_paragraph(paragraph, max_chars))
        elif len(buffer) + len(paragraph) < max_chars:
            buffer += paragraph + "\n"
        else:
            subchunks.append(buffer.strip())
            buffer = paragraph + "\n"

    if buffer.strip():
        subchunks.append(buffer.strip())

    return subchunks
