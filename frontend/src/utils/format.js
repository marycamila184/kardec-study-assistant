// "Q.N" is O Livro dos Espíritos vocabulary (its entries are questões,
// globally numbered); the other works call their numbered entries itens.
export function formatItemRef(book, itemNumber) {
  return book === 'O Livro dos Espíritos' ? `Q.${itemNumber}` : `item ${itemNumber}`;
}

const LIVRO_DOS_ESPIRITOS = 'O Livro dos Espíritos';

// Stored as "CAPÍTULO V". Shown as "cap. V": the citation is a locator beside a
// book title, not a heading, and full caps shouts in an 11px chip.
export function formatChapterRef(chapterRef) {
  if (!chapterRef) return null;
  const m = String(chapterRef).match(/^CAP[ÍI]TULO\s+(.+)$/i);
  return m ? `cap. ${m[1]}` : String(chapterRef);
}

/**
 * A citation a reader can actually look up.
 *
 * Item numbers restart every chapter in O Evangelho Segundo o Espiritismo,
 * O Céu e o Inferno **and A Gênese** — "A Gênese, item 1" matches eighteen
 * different passages — so the chapter is part of the reference, not a detail.
 * (Only Médiuns and O Livro dos Espíritos number their entries globally.)
 *
 * O Livro dos Espíritos is the exception that omits it: its questões are
 * unique across the whole work, and its "CAPÍTULO I" repeats in several parts,
 * so a chapter would add ambiguity instead of removing it.
 *
 * Takes the pieces explicitly because the API names them inconsistently:
 * `Source.chapter` is the chapter *title* while `Source.chapter_ref` is
 * "CAPÍTULO V", but `RelatedItem.chapter` is the ref.
 */
export function formatSourceRef({ book, chapterRef, itemNumber }) {
  const parts = [book];
  const cap = book === LIVRO_DOS_ESPIRITOS ? null : formatChapterRef(chapterRef);
  if (cap) parts.push(cap);
  if (itemNumber) parts.push(formatItemRef(book, itemNumber));
  return parts.join(', ');
}

/**
 * The human chapter name, or null when there is nothing worth showing.
 *
 * Book preambles carry the book's own title as their chapter_title, which is
 * how a citation ended up reading "O Livro dos Espíritos — O LIVRO DOS
 * ESPÍRITOS". Compared case- and accent-insensitively so the all-caps stored
 * form still matches the book name.
 */
export function chapterTitleOf({ book, chapterTitle }) {
  if (!chapterTitle) return null;
  const norm = (s) => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
  return norm(chapterTitle) === norm(book) ? null : chapterTitle;
}

/**
 * The machine chapter id a topic chip names, or null.
 *
 * Explorar's Evangelho topics are written "A humildade (cap. VII)", and that
 * chapter is the only thing standing between the topic and the Coletânea de
 * Preces, which wins a whole-book semantic search for almost any moral subject
 * — 60% of everything the ten topics retrieved (measured 2026-08-02). The
 * backend takes it as `chapter_filter`.
 *
 * Only the Evangelho chips carry this; the others name a question ("(Q.674)"),
 * which the backend resolves as a direct item lookup instead.
 */
export function chapterFilterFromTopic(label) {
  const match = /\(cap\.\s*([IVXL]+)\)/i.exec(label || '');
  return match ? `CAPÍTULO ${match[1].toUpperCase()}` : null;
}
