import React from 'react';

/**
 * The "Da Obra" cream section showing the original Kardec quote.
 * Sits on top of IABlock with no bottom border-radius (they join together).
 */
export default function ObraBlock({ obra, theme }) {
  if (!obra) return null;
  return (
    <>
      <div style={{
        background: theme.obraBg,
        border: `1px solid ${theme.obraBorder}`,
        borderBottom: 'none',
        borderRadius: '10px 10px 0 0',
        padding: '14px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <span style={{
            background: '#C8856A', color: 'white',
            fontSize: 7.5, fontWeight: 700, letterSpacing: '.1em',
            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase', flexShrink: 0,
          }}>Da Obra</span>
          <span style={{
            fontSize: 10, color: '#907060',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{obra.title}</span>
        </div>
        <div style={{
          fontFamily: "'Crimson Pro', serif",
          fontSize: 17, fontStyle: 'italic',
          color: theme.obraText, lineHeight: 1.75,
          whiteSpace: 'pre-wrap', marginBottom: 10,
        }}>{obra.quote}</div>
        <div style={{
          fontSize: 10, color: theme.subtext,
          fontFamily: "'Crimson Pro', serif", fontStyle: 'italic',
        }}>— {obra.citation}</div>
      </div>
      <div style={{ height: 1, background: theme.obraBorder }} />
    </>
  );
}
