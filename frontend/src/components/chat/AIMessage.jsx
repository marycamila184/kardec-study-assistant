import React from 'react';
import ObraBlock from './ObraBlock';
import IABlock from './IABlock';
import { useTypewriter } from '../../hooks/useTypewriter';

const BookIcon = ({ size = 11, color = 'white' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);

export default function AIMessage({
  msg, theme, fontSize,
  onShare, isMobile = false,
  showQuickActions = true,
  quickActions = [],
  onQuickAction,
  // Always undefined now — Refletir is switched off for production, the mode
  // is disconnected, not deleted; App.jsx no longer wires
  // handleReflectionQuestionClick. Kept + forwarded to IABlock (which guards
  // on it) rather than threaded out, so re-enabling Refletir is a one-line
  // change. See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
  onReflectionQuestionClick,
  suggestedQuestions = [],
  onSuggestedQuestionClick,
  footerAction = null,
  children,
}) {
  // A citação da obra revelava de uma vez enquanto a resposta digitava, então
  // o trecho do dia aparecia inteiro e a explicação vinha devagar logo abaixo.
  // Agora as duas usam o mesmo relógio, em sequência: primeiro a passagem,
  // depois o que a IA diz sobre ela — que é a ordem em que se lê.
  // A resposta do /chat agora chega em pedaços pelo stream, então o texto já
  // aparece progressivamente por conta própria: revelá-lo de novo com o
  // temporizador o faria começar do zero quando o `done` substitui o texto.
  // Histórico (fromCache) continua aparecendo inteiro, como antes.
  const noReveal = !!msg.fromCache || !!msg.streaming || !!msg.streamed;

  const quote = msg.obra?.quote || '';
  const revealedQuote = useTypewriter(quote, { key: msg.id, skip: noReveal });
  const quoteDone = revealedQuote.length >= quote.length;

  const revealedText = useTypewriter(msg.ia, {
    key: msg.id,
    skip: noReveal,
    start: quoteDone,
  });
  // Enquanto o stream corre a mensagem ainda está chegando: compartilhar ou
  // oferecer os botões de seguimento em cima de meia resposta seria errado.
  const isRevealing =
    !!msg.streaming || !quoteDone || revealedText.length < (msg.ia || '').length;

  return (
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', animation: 'fade-up .3s ease' }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', background: '#6B9BB8',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, marginTop: 2,
      }}>
        <BookIcon />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {msg.hasDaObra && (
          <ObraBlock obra={{ ...msg.obra, quote: revealedQuote }} theme={theme}
            onShare={onShare && !isRevealing ? onShare : undefined}
            compact={isMobile}
          />
        )}
        <IABlock
          msg={msg} theme={theme} fontSize={fontSize}
          revealedText={revealedText} isRevealing={isRevealing}
          showQuickActions={showQuickActions} quickActions={quickActions}
          onQuickAction={onQuickAction}
          // Forwarded as always-undefined; see comment on the prop above.
          onReflectionQuestionClick={onReflectionQuestionClick}
          suggestedQuestions={suggestedQuestions}
          onSuggestedQuestionClick={onSuggestedQuestionClick}
          footerAction={footerAction}
        />
        {!isRevealing && children}
      </div>
    </div>
  );
}
