import React from 'react';

const SITUATIONS = [
  { icon: '😢', label: 'Perda de alguém querido', text: 'Perdi alguém que eu amava e estou sofrendo muito com essa perda.' },
  { icon: '👨‍👩‍👧', label: 'Conflito familiar', text: 'Estou vivendo um conflito familiar que está me machucando.' },
  { icon: '😟', label: 'Ansiedade ou medo do futuro', text: 'Estou sentindo muita ansiedade e medo em relação ao futuro.' },
  { icon: '🙏', label: 'Gratidão e um momento de alegria', text: 'Quero refletir sobre um momento de alegria e gratidão que estou vivendo.' },
];

/**
 * "Refletir sobre uma Situação" entry screen — architecturally parallel to
 * EstudarPicker for the Estudar uma Obra flow. Button-only: the user picks a
 * starting situation, then continues the reflection via clicking AI-suggested
 * follow-up question buttons (see IABlock).
 * Props:
 *   theme
 *   onSubmit — (situationText: string) => void
 */
export default function RefletirPicker({ theme, onSubmit }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 22, fontWeight: 600, color: theme.text, marginBottom: 6 }}>
          Refletir sobre uma Situação
        </div>
        <div style={{ fontSize: 14, color: theme.subtext, lineHeight: 1.65 }}>
          Escolha o que mais se aproxima do que está vivendo e veja essa situação pela lente da doutrina espírita — sem conselhos, só reflexão.
        </div>
      </div>

      <div>
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
    </div>
  );
}
