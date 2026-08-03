import React from 'react';
import { useEscapeKey } from '../../hooks/useEscapeKey';
import { formatSourceRef, chapterTitleOf } from '../../utils/format';

/**
 * Citation excerpt modal — shows the retrieved passage behind a source chip.
 *
 * This is where a reader who wants to find the passage in their own copy comes
 * to read the reference, so it carries the chapter name as well as the number.
 *
 * Props:
 *   source  — { book, chapter, chapter_ref, item_number, excerpt } | null
 *             (`chapter` is the chapter *title*; `chapter_ref` is "CAPÍTULO V")
 *   theme
 *   onClose — () => void
 */
export default function SourceModal({ source, theme, onClose }) {
  useEscapeKey(onClose, !!source);
  if (!source) return null;

  const reference = formatSourceRef({
    book: source.book,
    chapterRef: source.chapter_ref,
    itemNumber: source.item_number,
  });
  const chapterTitle = chapterTitleOf({ book: source.book, chapterTitle: source.chapter });

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'rgba(0,0,0,.5)',
    }} onClick={onClose}>
      {/* Capped and scrollable, the same shape RelatedItemsModal already uses.
          Without the cap the card grows to whatever the excerpt needs, and an
          excerpt is a whole item — O Céu e o Inferno I PARTE cap. VIII item 2
          is thirteen subchunks. On a phone that runs off both ends of the
          screen, and neither the card nor the backdrop scrolls, so the passage
          simply cannot be read. The header stays put and only the passage
          scrolls, so the close button is always reachable. */}
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 480, width: '100%', maxHeight: '80vh', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 48px rgba(0,0,0,.3)',
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          padding: '16px 18px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Fonte citada</div>
          <button onClick={onClose} aria-label="Fechar" style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 20, color: theme.subtext, padding: '0 4px', lineHeight: 1,
          }}>×</button>
        </div>

        <div style={{ padding: '20px 18px', overflowY: 'auto' }}>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 16, fontStyle: 'italic',
            color: theme.text, lineHeight: 1.7, marginBottom: 14,
          }}>"{source.excerpt || 'Trecho não disponível.'}"</div>
          <div style={{ fontSize: 11, color: theme.text, lineHeight: 1.6 }}>
            Retirado de: {reference}
            {chapterTitle && (
              <div style={{
                fontFamily: "'Crimson Pro', serif", fontSize: 12.5,
                fontStyle: 'italic', marginTop: 3,
              }}>{chapterTitle}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
