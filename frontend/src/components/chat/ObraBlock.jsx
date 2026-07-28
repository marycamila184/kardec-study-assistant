import React from 'react';

const ShareIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
  </svg>
);

/**
 * The "Da Obra" cream section showing the original Kardec quote.
 * Sits on top of IABlock with no bottom border-radius (they join together).
 * Pass onShare to show a share button below the quote (Trecho do Dia only).
 */
export default function ObraBlock({ obra, theme, onShare, compact = false }) {
  if (!obra) return null;
  return (
    <>
      {/* The passage arrives whole, before the explanation starts, and used to
          land all at once over a card that was still empty. Easing it in takes
          the abruptness away without pretending Kardec's words are being
          written on the spot: the text is complete from the first frame, and
          only its opacity animates. Typing it out would simulate the model
          producing the source — which is exactly the separation this mode
          exists to keep visible. */}
      <div style={{
        background: theme.obraBg,
        border: `1px solid ${theme.obraBorder}`,
        borderBottom: 'none',
        borderRadius: '10px 10px 0 0',
        padding: '14px 16px',
        animation: 'fade-up .6s ease',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <span style={{
            background: '#C8856A', color: 'white',
            fontSize: 9, fontWeight: 700, letterSpacing: '.1em',
            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase', flexShrink: 0,
          }}>Da Obra</span>
          <span style={{
            fontSize: 12, color: '#907060',
            // minWidth: 0 is what makes the ellipsis work here. A flex item
            // does not shrink below its own content by default
            // (min-width: auto), so without this the text ignores the overflow
            // and bursts the card instead of truncating — visible on mobile,
            // where the work's reference does not fit the width.
            minWidth: 0,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{obra.title}</span>
        </div>
        <div style={{
          fontFamily: "'Crimson Pro', serif",
          fontSize: 19, fontStyle: 'italic',
          color: theme.obraText, lineHeight: 1.75,
          whiteSpace: 'pre-wrap', marginBottom: 10,
        }}>{obra.quote}</div>
        {onShare && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
            <button onClick={onShare} aria-label="Compartilhar" style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'transparent', border: '1px solid rgba(144,112,96,.3)',
              borderRadius: 6, padding: compact ? '4px 8px' : '4px 10px', cursor: 'pointer',
              color: '#907060', fontSize: 12, fontWeight: 500,
            }}>
              <ShareIcon />{!compact && ' Compartilhar'}
            </button>
          </div>
        )}
      </div>
      <div style={{ height: 1, background: theme.obraBorder }} />
    </>
  );
}
