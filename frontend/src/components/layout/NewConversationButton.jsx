// frontend/src/components/layout/NewConversationButton.jsx
import React, { useState, useEffect, useRef } from 'react';
import { MODES } from '../../constants/modes';

/**
 * Split button: the body opens the home launcher, the caret opens a shortcut
 * menu of the same three modes.
 *
 * The menu is an acceleration of the home screen, not a replacement — the home
 * stays the canonical launcher. Both render from the same MODES array, so they
 * can never disagree about which modes exist or what they are called.
 *
 * Props:
 *   onNewConvo — () => void  (opens the home launcher)
 *   onPickMode — (modeId: string) => void  (shortcut straight into a mode)
 */
export default function NewConversationButton({ onNewConvo, onPickMode }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  // Close on outside click and on Escape — a menu that traps focus in a
  // 300px sidebar is worse than no menu.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const seg = {
    background: 'rgba(255,255,255,.18)',
    border: '1px solid rgba(255,255,255,.32)',
    color: 'white', font: 'inherit', fontSize: 13, fontWeight: 600,
    cursor: 'pointer', padding: '9px 12px',
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative', padding: '0 10px 4px' }}>
      <div style={{ display: 'flex' }}>
        <button
          onClick={() => { setOpen(false); onNewConvo(); }}
          style={{
            ...seg, flex: 1, borderRadius: '8px 0 0 8px', borderRight: 'none',
            display: 'flex', alignItems: 'center', gap: 7,
          }}
        >
          <span style={{ fontSize: 15, lineHeight: 1 }}>+</span>
          Nova conversa
        </button>
        <button
          onClick={() => setOpen(o => !o)}
          aria-label="Escolher um modo"
          aria-expanded={open}
          aria-haspopup="menu"
          style={{ ...seg, borderRadius: '0 8px 8px 0', padding: '9px 10px' }}
        >
          ▾
        </button>
      </div>

      {open && (
        <div role="menu" style={{
          position: 'absolute', top: '100%', left: 10, right: 10, zIndex: 30,
          background: '#5A8AA6', border: '1px solid rgba(255,255,255,.28)',
          borderRadius: 8, padding: 4, marginTop: 4,
          boxShadow: '0 6px 18px rgba(0,0,0,.28)',
        }}>
          {MODES.map(m => (
            <button
              key={m.id}
              role="menuitem"
              onClick={() => { setOpen(false); onPickMode(m.id); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 9, width: '100%',
                background: 'transparent', border: 'none', font: 'inherit',
                color: 'white', fontSize: 13, textAlign: 'left',
                padding: '8px 9px', borderRadius: 6, cursor: 'pointer',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,.16)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontSize: 15 }}>{m.icon}</span>
              {m.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
