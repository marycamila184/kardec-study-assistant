import React from 'react';

const TABS = [
  { id: 'estudar',  label: 'Estudar' },
  { id: 'duvida',   label: 'Dúvida' },
  { id: 'refletir', label: 'Refletir' },
];

export default function MobileBottomNav({ mode, onChange }) {
  const base = {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    gap: 3, cursor: 'pointer', padding: '5px 14px', borderRadius: 7,
  };
  return (
    <div style={{
      height: 58, background: '#6B9BB8',
      display: 'flex', alignItems: 'center', justifyContent: 'space-around',
      padding: '0 4px', flexShrink: 0, borderTop: '1px solid rgba(255,255,255,.12)',
    }}>
      {TABS.map(t => (
        <div key={t.id} onClick={() => onChange(t.id)} style={{
          ...base,
          background: mode === t.id ? 'rgba(255,255,255,.2)' : 'transparent',
          opacity: mode === t.id ? 1 : 0.55,
        }}>
          <span style={{ fontSize: 9, color: 'white', fontWeight: 500 }}>{t.label}</span>
        </div>
      ))}
    </div>
  );
}
