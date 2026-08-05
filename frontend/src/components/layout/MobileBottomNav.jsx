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

const SunIcon = ({ active }) => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
    stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="4"/>
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
  </svg>
);

// Every tab here navigates, and "Trecho" is a tab because it can now satisfy
// that rule. The old "Hoje" tab could not: tapping it generated a conversation
// and left the reader in Dúvida, with the bar highlighting a tab they had not
// tapped, because its isActive was hardcoded false — there was no screen for it
// to be active on. There still isn't a separate screen, but there is a distinct
// state: handleStudyTrecho sets convoId to `trecho_…`, so `trechoActive` is
// true exactly while the daily passage is the open conversation. That is what
// the old tab was missing, and it is why it also *suppresses* Dúvida below —
// the passage runs in duvida mode, and two lit tabs would be the same lie in a
// new place.
//
// It is an SVG sun rather than the ☀️ TrechoCard uses: the other two tabs are
// line icons, and one emoji among them reads as a different kind of control.
const TABS = [
  { id: 'estudar',  label: 'Estudar',  Icon: BookOpenIcon },
  { id: 'duvida',   label: 'Dúvida',   Icon: ChatIcon },
  { id: 'trecho',   label: 'Trecho',   Icon: SunIcon },
  // Refletir is switched off for production — the mode is disconnected, not
  // deleted. See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
  // { id: 'refletir', label: 'Refletir', Icon: MirrorIcon },
];

export default function MobileBottomNav({
  mode, onChange, onStudyTrecho, trechoActive = false, trechoEnabled = true,
}) {
  const handleTab = (id) => {
    if (id === 'trecho') {
      if (trechoEnabled) onStudyTrecho?.();
      return;
    }
    onChange(id);
  };

  const isActive = (id) =>
    id === 'trecho' ? trechoActive : mode === id && !trechoActive;

  return (
    <div style={{
      height: 62, background: '#6B9BB8',
      display: 'flex', alignItems: 'stretch',
      flexShrink: 0, borderTop: '1px solid rgba(255,255,255,.14)',
    }}>
      {TABS.map(({ id, label, Icon }) => {
        const active = isActive(id);
        // Only "Trecho" can be unavailable, and only while /evangelho has not
        // landed. Rendered dim-but-present rather than removed: a tab that
        // appears once a fetch resolves is a tab the reader stops looking for.
        const disabled = id === 'trecho' && !trechoEnabled;
        return (
          <button
            key={id}
            onClick={() => handleTab(id)}
            disabled={disabled}
            aria-current={active ? 'true' : undefined}
            style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 4,
              border: 'none', cursor: disabled ? 'default' : 'pointer',
              background: active ? 'rgba(255,255,255,.18)' : 'transparent',
              borderTop: active ? '2px solid rgba(255,255,255,.7)' : '2px solid transparent',
              opacity: disabled ? 0.32 : active ? 1 : 0.6,
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
