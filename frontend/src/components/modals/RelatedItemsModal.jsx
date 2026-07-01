import React, { useState } from 'react';

/**
 * Related items modal — lists items connected to the current passage.
 * Props:
 *   modal        — { items: [{book, item_number, preview, conexao}] } | null
 *   theme
 *   onClose      — () => void
 *   onSelectItem — (item) => void, called when a row is clicked
 */
export default function RelatedItemsModal({ modal, theme, onClose, onSelectItem }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (!modal) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'rgba(0,0,0,.5)',
    }} onClick={onClose}>
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 480, width: '100%', maxHeight: '80vh', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 48px rgba(0,0,0,.3)',
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          padding: '16px 18px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Leituras relacionadas</div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 20, color: theme.subtext, padding: '0 4px', lineHeight: 1,
          }}>×</button>
        </div>

        <div style={{ overflowY: 'auto', padding: '8px 10px' }}>
          {modal.items.map((item, i) => (
            <div
              key={i}
              onClick={() => onSelectItem(item)}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              style={{
                cursor: 'pointer', borderRadius: 10, padding: '12px 10px',
                background: hoveredIndex === i ? theme.cardBg : 'transparent',
                transition: 'background .15s',
              }}
            >
              <div style={{ fontSize: 12.5, fontWeight: 600, color: theme.text, marginBottom: 4 }}>
                {item.book} — Q.{item.item_number}
              </div>
              {item.conexao && (
                <div style={{ fontSize: 11.5, color: theme.qasText, marginBottom: 4, lineHeight: 1.5 }}>
                  {item.conexao}
                </div>
              )}
              <div style={{
                fontFamily: "'Crimson Pro', serif", fontSize: 13, fontStyle: 'italic',
                color: theme.subtext, lineHeight: 1.6,
              }}>"{item.preview}…"</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
