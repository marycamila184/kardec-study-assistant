import re
from .chunking import split_into_subchunks

def parse_md_to_json(md_text: str, book_name: str, max_chars: int = 2000):
    """
    Parses Spiritism Markdown into JSON.
    Works for books with or without numbered items.
    """

    lines = md_text.split("\n")

    part = None
    chapter = None
    chapter_title = None

    results = []
    current_section = None
    content_buffer = []
    footnotes = []

    note_mode = False
    note_number = None
    note_buffer = []

    section_counter = 1  # pseudo-item number for unnumbered sections

    def save_section():
        nonlocal section_counter
        if content_buffer:
            full_text = "\n".join(content_buffer).strip()
            subchunks = split_into_subchunks(full_text, max_chars)
            for idx, chunk in enumerate(subchunks, start=1):
                results.append({
                    "book": book_name,
                    "part": part,
                    "chapter": chapter,
                    "chapter_title": chapter_title,
                    "item_number": current_section if current_section else f"section-{section_counter}",
                    "subchunk_index": idx,
                    "total_subchunks": len(subchunks),
                    "content": chunk,
                    "footnotes": footnotes
                })
            section_counter += 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Footnote detection
        if re.match(r'^_{3,}', line):
            note_mode = True
            note_number = None
            note_buffer = []
            continue

        # Footnote content
        if note_mode:
            match_note = re.match(r'^(\d+)\s+(.*)', line)
            if note_number is None and match_note:
                note_number = match_note.group(1)
                note_buffer.append(match_note.group(2))
                continue

            # Stop footnote when a new header or section appears
            if line.startswith("#") or re.match(r'^\d+\.\s-', line):
                if note_number:
                    footnotes.append({
                        "number": note_number,
                        "content": " ".join(note_buffer).strip()
                    })
                note_mode = False
                note_number = None
                note_buffer = []

            else:
                note_buffer.append(line)
                continue

        # Detect Part
        if line.startswith("#") and "PARTE" in line:
            save_section()
            part = line.replace("#", "").strip()
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Detect Chapter
        if line.startswith("#") and "CAPÍTULO" in line:
            save_section()
            chapter = line.replace("#", "").strip()
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Detect Chapter Title
        if line.startswith("#") and "PARTE" not in line and "CAPÍTULO" not in line:
            save_section()
            chapter_title = line.replace("#", "").strip()
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Numbered item
        match_item = re.match(r'^(\d+)\.\s-', line)
        if match_item:
            save_section()
            current_section = match_item.group(1)
            content_buffer = [line]
            footnotes = []
            continue

        # New unnumbered header treated as section boundary
        if line.startswith("#"):
            save_section()
            current_section = line.replace("#", "").strip()
            content_buffer = []
            footnotes = []
            continue

        # Normal content
        content_buffer.append(line)

    save_section()  # save last section

    return results
