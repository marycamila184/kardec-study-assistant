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

const MirrorIcon = ({ active }) => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
    stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3C8 3 5 6 5 9c0 4 4 8 7 11 3-3 7-7 7-11 0-3-3-6-7-6z"/>
    <line x1="12" y1="3" x2="12" y2="20"/>
  </svg>
);

const SunIcon = ({ active }) => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="none"
    stroke="white" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/>
    <line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
);

const TABS = [
  { id: 'estudar',  label: 'Estudar',  Icon: BookOpenIcon },
  { id: 'duvida',   label: 'Dúvida',   Icon: ChatIcon },
  { id: 'refletir', label: 'Refletir', Icon: MirrorIcon },
  { id: 'hoje',     label: 'Hoje',     Icon: SunIcon },
];

export default function MobileBottomNav({ mode, onChange, onStudyTrecho }) {
  const handleTab = (id) => {
    if (id === 'hoje') {
      onStudyTrecho?.();
    } else {
      onChange(id);
    }
  };

  const isActive = (id) => id === 'hoje' ? false : mode === id;

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
