import React from 'react';
import ObraBlock from './ObraBlock';
import IABlock from './IABlock';

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
  // No simulated reveal any more: text that appears gradually is text the
  // model is actually still producing, word by word, over the stream. Anything
  // that does not stream appears whole, which is the truth about how it
  // arrived.
  // While the stream runs the message is still on its way: sharing it, or
  // offering the follow-up buttons over half an answer, would be wrong.
  const isStreaming = !!msg.streaming;

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
          <ObraBlock obra={msg.obra} theme={theme}
            onShare={onShare && !isStreaming ? onShare : undefined}
            compact={isMobile}
          />
        )}
        <IABlock
          msg={msg} theme={theme} fontSize={fontSize}
          text={msg.ia} isStreaming={isStreaming}
          showQuickActions={showQuickActions} quickActions={quickActions}
          onQuickAction={onQuickAction}
          // Forwarded as always-undefined; see comment on the prop above.
          onReflectionQuestionClick={onReflectionQuestionClick}
          suggestedQuestions={suggestedQuestions}
          onSuggestedQuestionClick={onSuggestedQuestionClick}
          footerAction={footerAction}
        />
        {!isStreaming && children}
      </div>
    </div>
  );
}
