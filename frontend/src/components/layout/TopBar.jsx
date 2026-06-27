import React from 'react';

const MODE_META = {
  estudar:  { title: 'Estudar uma Obra',  desc: 'Consulte questões, capítulos e temas específicos' },
  duvida:   { title: 'Tirar uma Dúvida',  desc: 'Perguntas abertas fundamentadas nas obras de Kardec' },
  refletir: { title: 'Refletir',           desc: 'Relacione situações da vida aos ensinamentos da doutrina' },
};

const GearIcon = ({ color }) => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
);

export default function TopBar({ mode, theme, onOpenSettings }) {
  const meta = MODE_META[mode] || MODE_META.duvida;
  return (
    <div style={{
      height: 58, padding: '0 20px',
      borderBottom: `1px solid ${theme.headerBorder}`,
      display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      background: theme.headerBg,
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: '50%', background: '#6B9BB8',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
          stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
        </svg>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: "'Crimson Pro', serif", fontSize: 15, fontWeight: 600, color: theme.text,
        }}>{meta.title}</div>
        <div style={{ fontSize: 10.5, color: theme.subtext, marginTop: 1 }}>{meta.desc}</div>
      </div>
      <button onClick={onOpenSettings} title="Configurações" style={{
        width: 34, height: 34, borderRadius: 8,
        background: 'transparent', border: `1px solid ${theme.headerBorder}`,
        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <GearIcon color={theme.subtext} />
      </button>
    </div>
  );
}
