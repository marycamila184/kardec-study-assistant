import React, { useState } from 'react';
import SourceModal from '../modals/SourceModal';
import { BRAND_TERRACOTTA } from '../../constants/theme';
import { renderInlineMarkdown } from '../../utils/inlineMarkdown';
import { formatItemRef } from '../../utils/format';

/**
 * The "Da IA" block containing the explanation text, historical context,
 * and optional quick action pills. Reveal state (`revealedText`/`isRevealing`)
 * is owned by AIMessage and passed down so follow-up buttons (rendered as
 * AIMessage's `children`) can gate on it too.
 */
export default function IABlock({
  msg, theme, fontSize = '13px',
  revealedText, isRevealing,
  showQuickActions = true,
  quickActions = [],
  onQuickAction,
  onReflectionQuestionClick,
  suggestedQuestions = [],
  onSuggestedQuestionClick,
  footerAction = null,
}) {
  const [openSource, setOpenSource] = useState(null);
  const [footerHover, setFooterHover] = useState(false);

  return (
    <div style={{
      background: theme.cardBg,
      border: `1px solid ${theme.cardBorder}`,
      borderTop: 'none',
      borderRadius: '0 0 10px 10px',
      padding: '13px 16px',
    }}>
      {(msg.hasDaObra || msg.isReflection) && (
        <div style={{ marginBottom: 10 }}>
          <span style={{
            background: msg.isReflection ? BRAND_TERRACOTTA : '#6B9BB8', color: 'white',
            fontSize: 9, fontWeight: 700, letterSpacing: '.1em',
            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
          }}>{msg.isReflection ? '🪞 Reflexão' : 'Da IA'}</span>
        </div>
      )}

      {msg.isReflection && msg.opening && (
        <div style={{
          fontFamily: "'Crimson Pro', serif", fontStyle: 'italic', fontSize: 15,
          color: BRAND_TERRACOTTA, lineHeight: 1.6, marginBottom: 10,
        }}>{renderInlineMarkdown(msg.opening)}</div>
      )}

      <div style={{
        fontSize, color: theme.text, lineHeight: 1.78, whiteSpace: 'pre-wrap',
      }}>{renderInlineMarkdown(revealedText)}</div>

      {!isRevealing && msg.isReflection && !msg.isClosing && msg.reflectionQuestions?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
          {msg.reflectionQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => onReflectionQuestionClick?.(q)}
              style={{
                background: 'rgba(200,133,106,.08)', border: `1px solid rgba(200,133,106,.25)`,
                borderRadius: 8, padding: '8px 12px', fontSize: 13, color: theme.text, lineHeight: 1.5,
                textAlign: 'left', cursor: 'pointer', font: 'inherit', width: '100%',
              }}
            >{renderInlineMarkdown(q)}</button>
          ))}
        </div>
      )}

      {/* Follow-up question chips (Tirar uma Dúvida) — tap sends the question */}
      {!isRevealing && suggestedQuestions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
          {suggestedQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => onSuggestedQuestionClick?.(q)}
              style={{
                background: 'rgba(107,155,184,.08)', border: '1px solid rgba(107,155,184,.25)',
                borderRadius: 8, padding: '8px 12px', fontSize: 13, color: theme.text, lineHeight: 1.5,
                textAlign: 'left', cursor: 'pointer', font: 'inherit', width: '100%',
              }}
            >{renderInlineMarkdown(q)}</button>
          ))}
        </div>
      )}

      {!isRevealing && msg.sources?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8 }}>
          {msg.sources.map((s, i) => (
            <button key={i} onClick={() => setOpenSource(s)} style={{
              background: 'transparent',
              border: `1px solid ${theme.cardBorder}`,
              color: theme.subtext, fontSize: 11,
              padding: '3px 10px', borderRadius: 12,
              cursor: 'pointer', fontWeight: 500,
            }}>
              📖 {s.item_number
                ? `${s.book}, ${formatItemRef(s.book, s.item_number)}`
                : (s.chapter ? `${s.book} — ${s.chapter}` : s.book)}
            </button>
          ))}
        </div>
      )}

      {!isRevealing && showQuickActions && quickActions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 10 }}>
          {quickActions.map((qa) => (
            <button key={qa.label} onClick={() => onQuickAction?.(qa.label)} style={{
              background: 'transparent',
              border: `1px solid ${theme.qasBorder}`,
              color: theme.qasText, fontSize: 14,
              padding: '5px 13px', borderRadius: 16,
              cursor: 'pointer', fontWeight: 500,
            }}>
              {qa.label}
            </button>
          ))}
        </div>
      )}

      {/* Cross-mode action attached as the card's footer strip; negative
          margins cancel the card's 13px 16px padding so it spans edge-to-edge
          and its corners close the card's bottom radius. */}
      {!isRevealing && footerAction && (
        <button
          onClick={footerAction.onClick}
          onMouseEnter={() => setFooterHover(true)}
          onMouseLeave={() => setFooterHover(false)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            width: 'calc(100% + 32px)', margin: '12px -16px -13px',
            padding: '10px 16px',
            background: footerHover ? 'rgba(128,128,128,.08)' : 'transparent',
            border: 'none', borderTop: `1px solid ${theme.cardBorder}`,
            borderRadius: '0 0 10px 10px', cursor: 'pointer',
            color: footerAction.color || '#4A7A98',
            fontSize: 13, fontWeight: 500, fontFamily: 'inherit', textAlign: 'left',
          }}
        >
          <span>{footerAction.label}</span>
          <span aria-hidden="true">→</span>
        </button>
      )}

      <SourceModal source={openSource} theme={theme} onClose={() => setOpenSource(null)} />
    </div>
  );
}
