import re
from .chunking import split_into_subchunks


def parse_md_to_json(md_text: str, book_name: str, max_chars: int = 2000):
    """
    Parses a Markdown file into structured JSON with hierarchical metadata
    and optional subchunk splitting.
    """

    lines = md_text.split("\n")

    part = None
    chapter = None
    chapter_title = None

    results = []
    current_item = None
    content_buffer = []
    footnotes = []

    note_mode = False
    note_number = None
    note_buffer = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # Start footnote section
        if line == "__________":
            note_mode = True
            note_number = None
            note_buffer = []
            continue

        # Footnote mode
        if note_mode:
            match_note = re.match(r'^(\d+)\s+(.*)', line)

            if note_number is None and match_note:
                note_number = match_note.group(1)
                note_buffer.append(match_note.group(2))
                continue

            if re.match(r'^\d+\.\s-', line):
                if note_number:
                    footnotes.append({
                        "number": note_number,
                        "content": " ".join(note_buffer).strip()
                    })

                note_mode = False
                note_number = None
                note_buffer = []

            else:
                if line.startswith("#"):
                    continue
                note_buffer.append(line)
                continue

        # Detect Part
        if line.startswith("#") and "PARTE" in line:
            part = line.replace("#", "").strip()
            continue

        # Detect Chapter
        if line.startswith("#") and "CAPÍTULO" in line:
            chapter = line.replace("#", "").strip()
            continue

        # Detect Chapter Title
        if line.startswith("#") and "PARTE" not in line and "CAPÍTULO" not in line:
            chapter_title = line.replace("#", "").strip()
            continue

        # Detect New Item
        match_item = re.match(r'^(\d+)\.\s-', line)
        if match_item:

            if current_item:
                full_text = "\n".join(content_buffer).strip()
                subchunks = split_into_subchunks(full_text, max_chars)

                for index, chunk in enumerate(subchunks, start=1):
                    results.append({
                        "book": book_name,
                        "part": part,
                        "chapter": chapter,
                        "chapter_title": chapter_title,
                        "item_number": current_item,
                        "subchunk_index": index,
                        "total_subchunks": len(subchunks),
                        "content": chunk,
                        "footnotes": footnotes
                    })

            current_item = match_item.group(1)
            content_buffer = [line]
            footnotes = []
            continue

        if current_item:
            content_buffer.append(line)

    # Save last item
    if current_item:
        full_text = "\n".join(content_buffer).strip()
        subchunks = split_into_subchunks(full_text, max_chars)

        for index, chunk in enumerate(subchunks, start=1):
            results.append({
                "book": book_name,
                "part": part,
                "chapter": chapter,
                "chapter_title": chapter_title,
                "item_number": current_item,
                "subchunk_index": index,
                "total_subchunks": len(subchunks),
                "content": chunk,
                "footnotes": footnotes
            })

    return results
