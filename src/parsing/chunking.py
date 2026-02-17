
def split_into_subchunks(text: str, max_chars: int = 2000):
    """
    Splits long text into subchunks while preserving paragraph structure.
    """
    paragraphs = text.split("\n")
    subchunks = []
    buffer = ""

    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) < max_chars:
            buffer += paragraph + "\n"
        else:
            subchunks.append(buffer.strip())
            buffer = paragraph + "\n"

    if buffer.strip():
        subchunks.append(buffer.strip())

    return subchunks
