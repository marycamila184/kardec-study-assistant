import React, { useState } from 'react';
import SourceModal from '../modals/SourceModal';
import { Dots } from './LoadingDots';
// Refletir is switched off for production — the mode is disconnected, not
// deleted. BRAND_TERRACOTTA was only used for the "🪞 Reflexão" badge below,
// which is commented out along with it. See
// docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
// import { BRAND_TERRACOTTA } from '../../constants/theme';
import { renderInlineMarkdown } from '../../utils/inlineMarkdown';
import { formatSourceRef } from '../../utils/format';

/**
 * The "Da IA" block containing the explanation text, historical context,
 * and optional quick action pills. `isStreaming` is owned by AIMessage and
 * passed down so follow-up buttons (rendered as AIMessage's `children`) can
 * gate on it too: sources, chips and sharing stay hidden until the answer is
 * whole, since offering them over half a response would be wrong.
 */
export default function IABlock({
  msg, theme, fontSize = '13px',
  text, isStreaming,
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
      {/* Refletir is switched off for production — the mode is disconnected,
          not deleted. A legacy conversation saved before the switch-off can
          still carry msg.isReflection: true; it must render as plain answer
          text with no badge, since the terracotta "🪞 Reflexão" badge would
          identify a mode that no longer exists. See
          docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md */}
      {/* {(msg.hasDaObra || msg.isReflection) && ( */}
      {msg.hasDaObra && (
        <div style={{ marginBottom: 10 }}>
          <span style={{
            background: /* msg.isReflection ? BRAND_TERRACOTTA : */ '#6B9BB8', color: 'white',
            fontSize: 9, fontWeight: 700, letterSpacing: '.1em',
            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
          }}>{/* msg.isReflection ? '🪞 Reflexão' : */ 'Da IA'}</span>
        </div>
      )}

      {/* The Reflexivo's opening runs as the first paragraph of the answer, in
          the same type as the rest. It used to be set apart in serif italic
          terracotta, which read as a second voice speaking before the answer —
          a greeting card stapled to a letter. It is the same voice, so it is
          the same text. Joined into one block rather than styled to match, so
          the paragraph rhythm is the body's own and reflections already saved
          in a reader's history re-render the new way too. */}
      {/* The passage arrives before the explanation starts, so without this the
          card would sit empty and silent for the seconds before the first
          token — the wait moved rather than shrank. */}
      {isStreaming && !text ? <Dots /> : (
        <div style={{
          fontSize, color: theme.text, lineHeight: 1.78, whiteSpace: 'pre-wrap',
        }}>{renderInlineMarkdown(
          [msg.isReflection && msg.opening, text].filter(Boolean).join('\n\n')
        )}</div>
      )}

      {/* Refletir is switched off for production — the mode is disconnected,
          not deleted. A legacy conversation can still carry
          msg.reflectionQuestions, but onReflectionQuestionClick is now always
          undefined (App.jsx no longer wires handleReflectionQuestionClick) —
          without this guard these buttons would render and silently do
          nothing when clicked. Suppressed entirely rather than left dead. See
          docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md */}
      {/* {!isStreaming && msg.isReflection && !msg.isClosing && msg.reflectionQuestions?.length > 0 && (
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
      )} */}

      {/* Follow-up question chips (Tirar uma Dúvida) — tap sends the question */}
      {!isStreaming && suggestedQuestions.length > 0 && (
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

      {!isStreaming && msg.sources?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8 }}>
          {msg.sources.map((s, i) => (
            <button key={i} onClick={() => setOpenSource(s)} style={{
              background: 'transparent',
              border: `1px solid ${theme.cardBorder}`,
              color: theme.subtext, fontSize: 11,
              padding: '3px 10px', borderRadius: 12,
              cursor: 'pointer', fontWeight: 500,
            }}>
              📖 {formatSourceRef({
                book: s.book,
                chapterRef: s.chapter_ref,
                itemNumber: s.item_number,
              })}
            </button>
          ))}
        </div>
      )}

      {/* The chapter items the answer actually cited, resolved from its
          [item N] markers. When it cited none — which is most turns — the row
          is simply absent, and that is the honest outcome: the earlier version
          listed everything fed to the prompt under a heading claiming it had
          been used. Labelled neutrally as "itens do capítulo" because these are
          the chapter as retrieval returned it, verses and Kardec's commentary
          mixed, and nothing in the metadata separates the two. */}
      {!isStreaming && msg.chapterContext?.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: theme.subtext, marginBottom: 5 }}>
            Itens do capítulo citados nesta explicação
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {msg.chapterContext.map((c, i) => (
              <button key={i} onClick={() => setOpenSource(c)} style={{
                background: 'transparent',
                border: `1px solid ${theme.cardBorder}`,
                color: theme.subtext, fontSize: 11,
                padding: '3px 10px', borderRadius: 12,
                cursor: 'pointer', fontWeight: 500,
              }}>
                📖 {formatSourceRef({ book: c.book, itemNumber: c.item_number })}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isStreaming && showQuickActions && quickActions.length > 0 && (
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
      {!isStreaming && footerAction && (
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
