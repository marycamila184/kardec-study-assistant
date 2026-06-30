import React, { useState } from 'react';
import SourceModal from '../modals/SourceModal';

const ShareIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
  </svg>
);

/**
 * The "Da IA" block containing the explanation text, historical context,
 * share/fav buttons, and optional quick action pills.
 */
export default function IABlock({
  msg, theme, fontSize = '13px',
  onShare, onToggleFav, isFavorite,
  showQuickActions = true,
  quickActions = [],
  onQuickAction,
}) {
  const [openSource, setOpenSource] = useState(null);

  return (
    <div style={{
      background: theme.cardBg,
      border: `1px solid ${theme.cardBorder}`,
      borderTop: 'none',
      borderRadius: '0 0 10px 10px',
      padding: '13px 16px',
    }}>
      {msg.hasDaObra && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{
            background: '#6B9BB8', color: 'white',
            fontSize: 9, fontWeight: 700, letterSpacing: '.1em',
            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
          }}>Da IA</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {onShare && (
              <button onClick={() => onShare(msg)} style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                padding: '2px 4px', display: 'flex', alignItems: 'center',
                color: theme.subtext, borderRadius: 4,
              }}>
                <ShareIcon />
              </button>
            )}
            {onToggleFav && (
              <button onClick={() => onToggleFav(msg)} style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                padding: '2px 4px', fontSize: 20, lineHeight: 1,
                opacity: isFavorite ? 1 : 0.38,
              }}>
                {isFavorite ? '⭐' : '☆'}
              </button>
            )}
          </div>
        </div>
      )}

      <div style={{
        fontSize, color: theme.text, lineHeight: 1.78, whiteSpace: 'pre-wrap',
      }}>{msg.ia}</div>

      {msg.sources?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8 }}>
          {msg.sources.map((s, i) => (
            <button key={i} onClick={() => setOpenSource(s)} style={{
              background: 'transparent',
              border: `1px solid ${theme.cardBorder}`,
              color: theme.subtext, fontSize: 11,
              padding: '3px 10px', borderRadius: 12,
              cursor: 'pointer', fontWeight: 500,
            }}>
              📖 {s.item_number ? `${s.book}, Q.${s.item_number}` : s.book}
            </button>
          ))}
        </div>
      )}

      {showQuickActions && quickActions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 10 }}>
          {quickActions.map((qa) => (
            <button key={qa.label} onClick={() => onQuickAction?.(qa.label)} style={{
              background: 'transparent',
              border: `1px solid ${theme.qasBorder}`,
              color: theme.qasText, fontSize: 14,
              padding: '5px 13px', borderRadius: 16,
              cursor: 'pointer', fontWeight: 500,
            }}>
              {qa.label}
            </button>
          ))}
        </div>
      )}

      <SourceModal source={openSource} theme={theme} onClose={() => setOpenSource(null)} />
    </div>
  );
}
