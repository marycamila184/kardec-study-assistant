import { useState } from 'react';
import { sendFeedback } from '../../services/api';

// Só polegar, sem caixa de texto — escopo fechado na spec. Se a falta do "por
// quê" doer depois de ler os primeiros negativos ao lado das perguntas que os
// geraram, aí se acrescenta, com a informação na mão em vez de por suposição.
//
// O voto vale com ou sem consentimento: {turn_id, vote} não descreve pessoa,
// então recusar o banner não tira de ninguém a capacidade de dizer que a
// resposta foi ruim.
//
// Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
export default function FeedbackButtons({ turnId, theme }) {
  const [voted, setVoted] = useState(null);
  // Sem turno registrado não há o que votar — acontece no evento `source` do
  // stream, que chega antes de a resposta existir.
  if (!turnId) return null;

  const vote = (v) => () => {
    if (voted) return; // um voto por turno; trocar de ideia não é o caso de uso
    setVoted(v);
    sendFeedback(turnId, v);
  };

  const style = (v) => ({
    background: 'transparent',
    border: 'none',
    cursor: voted ? 'default' : 'pointer',
    padding: '2px 5px',
    lineHeight: 0,
    color: theme.subtext,
    // The chosen one stays legible, the other recedes. No colour, no fill: a
    // vote is a quiet aside, not something competing with the answer.
    opacity: voted ? (voted === v ? 0.85 : 0.2) : 0.5,
    fontFamily: 'inherit',
  });

  // Outline, not emoji. The emoji 👍/👎 render filled and coloured — on some
  // platforms in full skin tone — which made a two-pixel aside louder than the
  // citation links beside it. These inherit `color` and `currentColor`, so they
  // follow the theme in both modes.
  const Thumb = ({ down = false }) => (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round"
      style={down ? { transform: 'rotate(180deg)' } : undefined}
      aria-hidden="true"
    >
      <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3z" />
      <path d="M7 10l4.4-7.3a1.6 1.6 0 0 1 2.9 1.1L13.5 9h5.2a1.8 1.8 0 0 1 1.8 2.2l-1.5 7A2 2 0 0 1 17 20H7" />
    </svg>
  );

  return (
    <div style={{ display: 'flex', gap: 2, marginTop: 8, alignItems: 'center' }}>
      <button
        style={style('up')}
        onClick={vote('up')}
        disabled={!!voted}
        aria-label="Resposta útil"
        title="Resposta útil"
      >
        <Thumb />
      </button>
      <button
        style={style('down')}
        onClick={vote('down')}
        disabled={!!voted}
        aria-label="Resposta ruim"
        title="Resposta ruim"
      >
        <Thumb down />
      </button>
    </div>
  );
}
