import React from 'react';

const SITUATIONS = [
  { icon: '😢', label: 'Perda de alguém querido', text: 'Perdi alguém que eu amava e estou sofrendo muito com essa perda.' },
  { icon: '👨‍👩‍👧', label: 'Conflito familiar', text: 'Estou vivendo um conflito familiar que está me machucando.' },
  { icon: '😟', label: 'Ansiedade ou medo do futuro', text: 'Estou sentindo muita ansiedade e medo em relação ao futuro.' },
  { icon: '🙏', label: 'Gratidão e um momento de alegria', text: 'Quero refletir sobre um momento de alegria e gratidão que estou vivendo.' },
  { icon: '🤕', label: 'Doença ou sofrimento físico', text: 'Estou enfrentando uma doença ou sofrimento físico e isso está pesando em mim.' },
  { icon: '💔', label: 'Mágoa ou dificuldade em perdoar', text: 'Estou guardando mágoa ou raiva de alguém e sinto dificuldade em perdoar.' },
  { icon: '🌌', label: 'Dúvidas espirituais', text: 'Estou passando por dúvidas espirituais e queria refletir sobre isso.' },
  { icon: '🔀', label: 'Decisão difícil ou mudança de vida', text: 'Estou diante de uma decisão difícil ou uma grande mudança de vida.' },
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
      {/* No title here: the TopBar already names the mode. This line is the
          screen's instruction, which is different content. */}
      <div style={{ marginBottom: 22 }}>
        {/* theme.text, not subtext: this is now the screen's leading line,
            not a caption. subtext is 2.92:1 on the light background —
            below the 4.5:1 floor, and unreadable as primary copy. */}
        <div style={{ fontSize: 15.5, color: theme.text, lineHeight: 1.6, maxWidth: 620 }}>
          Escolha o que mais se aproxima do que está vivendo e veja essa situação pela lente da doutrina espírita — sem conselhos, só reflexão.
        </div>
      </div>

      <div>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Situações comuns</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
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
