import React from 'react';

const BookOpenIcon = ({ active }) => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
    stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);

const ChatIcon = ({ active }) => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
    stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);

// Refletir is switched off for production — the mode is disconnected, not
// deleted. See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
// const MirrorIcon = ({ active }) => (
//   <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
//     stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
//     <path d="M12 3C8 3 5 6 5 9c0 4 4 8 7 11 3-3 7-7 7-11 0-3-3-6-7-6z"/>
//     <line x1="12" y1="3" x2="12" y2="20"/>
//   </svg>
// );

// Every tab here navigates. "Hoje" used to sit alongside these and did not:
// tapping it generated a conversation and left the reader in Dúvida, with the
// bar highlighting a tab they had not tapped — its isActive was hardcoded false
// because there was no screen for it to be active on. The daily passage is now
// a card at the top of Estudar, which is a destination.
const TABS = [
  { id: 'estudar',  label: 'Estudar',  Icon: BookOpenIcon },
  { id: 'duvida',   label: 'Dúvida',   Icon: ChatIcon },
  // Refletir is switched off for production — the mode is disconnected, not
  // deleted. See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
  // { id: 'refletir', label: 'Refletir', Icon: MirrorIcon },
];

export default function MobileBottomNav({ mode, onChange }) {
  const handleTab = (id) => onChange(id);

  const isActive = (id) => mode === id;

  return (
    <div style={{
      height: 62, background: '#6B9BB8',
      display: 'flex', alignItems: 'stretch',
      flexShrink: 0, borderTop: '1px solid rgba(255,255,255,.14)',
    }}>
      {TABS.map(({ id, label, Icon }) => {
        const active = isActive(id);
        return (
          <button
            key={id}
            onClick={() => handleTab(id)}
            aria-current={active ? 'true' : undefined}
            style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 4,
              border: 'none', cursor: 'pointer',
              background: active ? 'rgba(255,255,255,.18)' : 'transparent',
              borderTop: active ? '2px solid rgba(255,255,255,.7)' : '2px solid transparent',
              opacity: active ? 1 : 0.6,
              transition: 'opacity .15s, background .15s',
              padding: '4px 0 6px',
            }}
          >
            <Icon active={active} />
            <span style={{ fontSize: 10, color: 'white', fontWeight: active ? 600 : 400, letterSpacing: '.01em' }}>
              {label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
