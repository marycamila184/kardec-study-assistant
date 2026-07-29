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
    fontSize: 14,
    padding: '2px 6px',
    lineHeight: 1,
    opacity: voted && voted !== v ? 0.25 : 1,
    fontFamily: 'inherit',
  });

  return (
    <div style={{ display: 'flex', gap: 2, marginTop: 8, alignItems: 'center' }}>
      {voted && (
        <span style={{ fontSize: 11, color: theme.subtext, marginRight: 6 }}>
          Obrigada
        </span>
      )}
      <button
        style={style('up')}
        onClick={vote('up')}
        disabled={!!voted}
        aria-label="Resposta útil"
        title="Resposta útil"
      >
        👍
      </button>
      <button
        style={style('down')}
        onClick={vote('down')}
        disabled={!!voted}
        aria-label="Resposta ruim"
        title="Resposta ruim"
      >
        👎
      </button>
    </div>
  );
}
