import re

from .chunking import split_into_subchunks


def parse_md_to_json(md_text: str, book_name: str, max_chars: int = 2000):
    """
    Parses Spiritism Markdown into JSON chunks.

    Footnote format: content with (N) reference, then:
        __________
        (N) Footnote text
        __________
    The separator pair acts as open/close delimiters. Each footnote belongs
    only to the element immediately preceding its opening separator — either a
    title heading (stored in title_footnotes) or a content paragraph (stored in
    footnotes on that specific chunk only).
    """
    lines = md_text.split("\n")

    part = None
    chapter = None
    chapter_title = None
    subsection = None
    title_footnotes = []  # footnotes for the current chapter_title or subsection

    results = []
    current_section = None  # current numbered item string, e.g. "3"
    section_counter = 1  # fallback counter for unnumbered sections

    # Segments: ordered list of (content_lines, footnotes) pairs for the current section.
    # Each footnote block closes a segment; the footnote(s) travel with that segment only.
    completed_segments = []
    current_lines = []  # content lines of the currently open segment

    # Footnote parsing state
    note_mode = False
    note_number = None
    note_buffer = []
    current_block_footnotes = []  # all footnotes accumulated within one ___…___ block
    footnote_belongs_to_title = False

    last_was_title = False  # True immediately after processing a heading line

    def flush_note():
        if note_number and note_buffer:
            return {"number": note_number, "content": " ".join(note_buffer).strip()}
        return None

    def save_section():
        nonlocal section_counter
        segs = completed_segments[:]
        if current_lines:
            segs.append((current_lines[:], []))

        all_chunks = []
        for seg_lines, seg_footnotes in segs:
            text = "\n".join(seg_lines).strip()
            if not text:
                continue
            for chunk in split_into_subchunks(text, max_chars):
                all_chunks.append((chunk, seg_footnotes))

        if not all_chunks:
            return

        item_num = current_section if current_section else f"section-{section_counter}"
        total = len(all_chunks)

        for idx, (chunk_text, chunk_footnotes) in enumerate(all_chunks, start=1):
            results.append(
                {
                    "book": book_name,
                    "part": part,
                    "chapter": chapter,
                    "chapter_title": chapter_title,
                    "title_footnotes": list(title_footnotes),
                    "subsection": subsection,
                    "item_number": item_num,
                    "subchunk_index": idx,
                    "total_subchunks": total,
                    "content": chunk_text,
                    "footnotes": chunk_footnotes,
                }
            )

        section_counter += 1

    def reset_section():
        nonlocal completed_segments, current_lines
        completed_segments = []
        current_lines = []

    def close_footnote_block():
        """Flush the current block into title_footnotes or a completed segment."""
        nonlocal title_footnotes
        note = flush_note()
        if note:
            current_block_footnotes.append(note)
        if current_block_footnotes:
            if footnote_belongs_to_title:
                title_footnotes = title_footnotes + current_block_footnotes
            else:
                completed_segments.append(
                    (current_lines[:], current_block_footnotes[:])
                )
                current_lines.clear()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Footnote separator — toggles open/close
        if re.match(r"^_{3,}", line):
            if not note_mode:
                note_mode = True
                note_number = None
                note_buffer = []
                current_block_footnotes = []
                # Title footnote: separator appears right after a heading with no content yet
                footnote_belongs_to_title = last_was_title and not current_lines
            else:
                close_footnote_block()
                note_mode = False
                note_number = None
                note_buffer = []
                current_block_footnotes = []
            continue

        # Inside a footnote block
        if note_mode:
            match_note = re.match(r"^\((\d+)\)\s+(.*)", line)
            if match_note:
                # New footnote number: save previous one into the block first
                note = flush_note()
                if note:
                    current_block_footnotes.append(note)
                note_number = match_note.group(1)
                note_buffer = [match_note.group(2)]
                continue
            # Malformed: structural line without a closing separator
            if line.startswith("#") or re.match(r"^\d+\.\s+", line):
                close_footnote_block()
                note_mode = False
                note_number = None
                note_buffer = []
                current_block_footnotes = []
                # Fall through to process this line as a heading or item
            else:
                note_buffer.append(line)
                continue

        # Part heading
        if line.startswith("#") and "PARTE" in line and "CAPÍTULO" not in line:
            save_section()
            reset_section()
            part = line.replace("#", "").strip()
            chapter_title = None
            subsection = None
            title_footnotes = []
            current_section = None
            last_was_title = True
            continue

        # Chapter heading
        if line.startswith("#") and "CAPÍTULO" in line:
            save_section()
            reset_section()
            chapter_str = line.replace("#", "").strip()
            if "PARTE" in chapter_str and " - " in chapter_str:
                chapter_str = chapter_str.split(" - ", 1)[1]
            chapter = chapter_str
            chapter_title = None
            subsection = None
            title_footnotes = []
            current_section = None
            last_was_title = True
            continue

        # Chapter title or subsection heading
        if line.startswith("#") and "PARTE" not in line and "CAPÍTULO" not in line:
            save_section()
            reset_section()
            heading = line.replace("#", "").strip()
            if chapter_title is None:
                chapter_title = heading
            else:
                subsection = heading
            title_footnotes = []
            current_section = None
            last_was_title = True
            continue

        # Numbered item
        match_item = re.match(r"^(\d+)\.\s+", line)
        if match_item:
            save_section()
            reset_section()
            current_section = match_item.group(1)
            current_lines = [line]
            last_was_title = False
            continue

        # Normal content
        current_lines.append(line)
        last_was_title = False

    save_section()
    return results
