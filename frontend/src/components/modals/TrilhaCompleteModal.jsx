import React from 'react';

/**
 * Shown once, right when a guided trilha is completed — before navigating
 * back to the picker. Offers a share action for the trilha's last passage.
 * Props:
 *   modal   — { trilha, lastMsg } | null
 *   theme
 *   onShare — () => void, opens ShareModal with lastMsg
 *   onClose — () => void, dismisses this modal and navigates to the picker
 */
export default function TrilhaCompleteModal({ modal, theme, onShare, onClose }) {
  if (!modal) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 95,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'rgba(0,0,0,.5)',
    }} onClick={onClose}>
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 380, width: '100%', padding: '32px 24px',
        textAlign: 'center', boxShadow: '0 8px 48px rgba(0,0,0,.3)',
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          background: 'rgba(107,155,184,.15)', border: '2px solid #6B9BB8',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 16px', fontSize: 24,
        }}>✨</div>
        <div style={{
          fontFamily: "'Crimson Pro', serif", fontSize: 20, fontWeight: 600,
          color: theme.text, marginBottom: 6,
        }}>Trilha concluída! 🌟</div>
        <div style={{ fontSize: 13, color: theme.subtext, marginBottom: 22, lineHeight: 1.6 }}>
          {modal.trilha?.title}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {modal.lastMsg && (
            <button onClick={onShare} style={{
              background: '#6B9BB8', color: 'white', border: 'none',
              padding: '10px 22px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>Compartilhar</button>
          )}
          <button onClick={onClose} style={{
            background: 'transparent', color: theme.subtext,
            border: `1px solid ${theme.headerBorder}`,
            padding: '10px 22px', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer',
          }}>Continuar</button>
        </div>
      </div>
    </div>
  );
}
