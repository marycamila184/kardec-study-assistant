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
    subsection = None

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
                    "subsection": subsection,
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

            # Stop footnote when a new header or numbered item appears
            if line.startswith("#") or re.match(r'^\d+\.\s+', line):
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

        # Detect Part (excludes combined "Xª PARTE - CAPÍTULO Y" headings)
        if line.startswith("#") and "PARTE" in line and "CAPÍTULO" not in line:
            save_section()
            part = line.replace("#", "").strip()
            chapter_title = None
            subsection = None
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Detect Chapter (handles "CAPÍTULO Y" and "Xª PARTE - CAPÍTULO Y")
        if line.startswith("#") and "CAPÍTULO" in line:
            save_section()
            chapter_str = line.replace("#", "").strip()
            if "PARTE" in chapter_str and " - " in chapter_str:
                chapter_str = chapter_str.split(" - ", 1)[1]
            chapter = chapter_str
            chapter_title = None
            subsection = None
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Detect Chapter Title or Subsection:
        # - first heading after a chapter → chapter_title
        # - subsequent headings within the same chapter → subsection
        if line.startswith("#") and "PARTE" not in line and "CAPÍTULO" not in line:
            save_section()
            heading = line.replace("#", "").strip()
            if chapter_title is None:
                chapter_title = heading
            else:
                subsection = heading
            current_section = None
            content_buffer = []
            footnotes = []
            continue

        # Numbered item (matches "N. text" with or without a leading dash)
        match_item = re.match(r'^(\d+)\.\s+', line)
        if match_item:
            save_section()
            current_section = match_item.group(1)
            content_buffer = [line]
            footnotes = []
            continue

        # Normal content
        content_buffer.append(line)

    save_section()  # save last section

    return results
