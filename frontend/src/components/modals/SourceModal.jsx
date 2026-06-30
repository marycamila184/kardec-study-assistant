import React from 'react';

/**
 * Citation excerpt modal — shows the retrieved passage behind a source chip.
 * Props:
 *   source  — { book, item_number, excerpt } | null
 *   theme
 *   onClose — () => void
 */
export default function SourceModal({ source, theme, onClose }) {
  if (!source) return null;

  const reference = source.item_number
    ? `${source.book}, Q.${source.item_number}`
    : source.book;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'rgba(0,0,0,.5)',
    }} onClick={onClose}>
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 480, width: '100%', boxShadow: '0 8px 48px rgba(0,0,0,.3)', overflow: 'hidden',
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          padding: '16px 18px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Fonte citada</div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 20, color: theme.subtext, padding: '0 4px', lineHeight: 1,
          }}>×</button>
        </div>

        <div style={{ padding: '20px 18px' }}>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 16, fontStyle: 'italic',
            color: theme.text, lineHeight: 1.7, marginBottom: 14,
          }}>"{source.excerpt || 'Trecho não disponível.'}"</div>
          <div style={{ fontSize: 11, color: theme.subtext }}>Retirado de: {reference}</div>
        </div>
      </div>
    </div>
  );
}
