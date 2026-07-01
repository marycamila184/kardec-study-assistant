import React, { useState } from 'react';

const SITUATIONS = [
  { icon: '😢', label: 'Perda de alguém querido', text: 'Perdi alguém que eu amava e estou sofrendo muito com essa perda.' },
  { icon: '👨‍👩‍👧', label: 'Conflito familiar', text: 'Estou vivendo um conflito familiar que está me machucando.' },
  { icon: '😟', label: 'Ansiedade ou medo do futuro', text: 'Estou sentindo muita ansiedade e medo em relação ao futuro.' },
  { icon: '🙏', label: 'Gratidão e um momento de alegria', text: 'Quero refletir sobre um momento de alegria e gratidão que estou vivendo.' },
];

/**
 * "Refletir sobre uma Situação" entry screen — architecturally parallel to
 * EstudarPicker for the Estudar uma Obra flow.
 * Props:
 *   theme
 *   onSubmit — (situationText: string) => void
 */
export default function RefletirPicker({ theme, onSubmit }) {
  const [text, setText] = useState('');

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 22, fontWeight: 600, color: theme.text, marginBottom: 6 }}>
          Refletir sobre uma Situação
        </div>
        <div style={{ fontSize: 14, color: theme.subtext, lineHeight: 1.65 }}>
          Descreva o que está vivendo e veja essa situação pela lente da doutrina espírita — sem conselhos, só reflexão.
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Situações comuns</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {SITUATIONS.map(s => (
            <button key={s.label} onClick={() => onSubmit(s.text)} style={{
              background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
              borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
              textAlign: 'left', display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <span style={{ fontSize: 20 }}>{s.icon}</span>
              <span style={{ fontSize: 14, color: theme.text, fontWeight: 500 }}>{s.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ borderTop: `1px solid ${theme.cardBorder}`, paddingTop: 14 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Ou descreva com suas palavras</div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Ex: Estou passando por um conflito familiar…"
          rows={3}
          style={{
            width: '100%', background: theme.inputBg, border: `1px solid ${theme.inputBorder}`,
            borderRadius: 10, padding: '10px 13px', fontSize: 14, color: theme.text,
            lineHeight: 1.55, resize: 'none', fontFamily: 'inherit', outline: 'none',
            boxSizing: 'border-box', marginBottom: 10,
          }}
        />
        <button
          onClick={() => { if (text.trim()) onSubmit(text.trim()); }}
          disabled={!text.trim()}
          style={{
            background: '#C8856A', color: 'white', border: 'none',
            padding: '9px 22px', borderRadius: 8, fontSize: 13.5, fontWeight: 600,
            cursor: text.trim() ? 'pointer' : 'not-allowed',
            opacity: text.trim() ? 1 : 0.5,
          }}
        >Refletir →</button>
      </div>
    </div>
  );
}
