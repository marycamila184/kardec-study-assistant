import React, { useState } from 'react';
import SourceModal from '../modals/SourceModal';
import FeedbackButtons from './FeedbackButtons';
import { Dots } from './LoadingDots';
// Refletir is switched off for production — the mode is disconnected, not
// deleted. BRAND_TERRACOTTA was only used for the "🪞 Reflexão" badge below,
// which is commented out along with it. See
// docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
// import { BRAND_TERRACOTTA } from '../../constants/theme';
import { renderInlineMarkdown } from '../../utils/inlineMarkdown';
import { formatSourceRef } from '../../utils/format';
import CitedText from './CitedText';

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
        }}>
          {/* Reflexivo's opening used to be joined into the same string as
              `text` before markdown rendering, via '\n\n'. inlineRefs'
              positions are counted into `text` alone, so joining them here
              would shift every ref by opening.length + 2 — kept as its own
              paragraph instead. Reflexivo is switched off in production
              (msg.isReflection is always false today); this only matters if
              it is reconnected. */}
          {msg.isReflection && msg.opening && (
            <div style={{ marginBottom: '1em' }}>{renderInlineMarkdown(msg.opening)}</div>
          )}
          {/* Durante o stream as posições ainda não valem: o texto é parcial e
              os refs chegam só com o `done`. Enquanto isso, texto puro. */}
          {isStreaming || !msg.inlineRefs?.length ? (
            renderInlineMarkdown(text)
          ) : (
            <CitedText
              text={text}
              refs={msg.inlineRefs}
              precision={msg.profile?.citation_precision}
              // isStudy, not hasDaObra: hasDaObra is also true on /chat when
              // free study resolves a named item, but /chat still runs a
              // normal cross-book retrieval alongside that and can cite
              // passages outside the resolved chapter — a bare "item N"
              // there would be ambiguous.
              insideOneChapter={msg.isStudy}
              onOpenSource={(ref) => setOpenSource({
                book: ref.book,
                chapter: ref.chapter_title,
                chapter_ref: ref.chapter_ref,
                item_number: ref.item_number,
                excerpt: ref.excerpt,
              })}
            />
          )}
        </div>
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

      {/* O que a prosa apontou virou link no texto; embaixo fica só o que
          sustentou a resposta sem ser apontado numa frase específica. Sem o
          filtro, cada fonte apareceria duas vezes. O rótulo existe porque uma
          fileira sem explicação, ao lado de links que se explicam, lê como
          sobra. */}
      {!isStreaming && (() => {
        const citados = new Set(
          (msg.inlineRefs || []).map((r) => `${r.book}|${r.item_number}`)
        );
        const restantes = (msg.sources || []).filter(
          (s) => !citados.has(`${s.book}|${s.item_number}`)
        );
        if (!restantes.length) return null;
        return (
          <div style={{ marginTop: 10 }}>
            {citados.size > 0 && (
              <div style={{ fontSize: 11, color: theme.subtext, marginBottom: 5 }}>
                Outras passagens usadas
              </div>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {restantes.map((s, i) => (
                <button key={i} onClick={() => setOpenSource(s)} style={{
                  background: 'transparent',
                  border: `1px solid ${theme.cardBorder}`,
                  color: theme.subtext, fontSize: 11,
                  padding: '3px 10px', borderRadius: 12,
                  cursor: 'pointer', fontWeight: 500,
                }}>
                  📖 {formatSourceRef({
                    book: s.book, chapterRef: s.chapter_ref, itemNumber: s.item_number,
                  })}
                </button>
              ))}
            </div>
          </div>
        );
      })()}

      {!isStreaming && msg.chapterContext?.length > 0 && (() => {
        // O que a explicação citou virou link no texto e sai daqui. O rótulo
        // "Outros itens deste capítulo" passa a ser literalmente verdade — e a
        // ordenação citados-primeiro perde a função, porque citado nenhum
        // sobra nesta lista.
        const citados = new Set((msg.inlineRefs || []).map((r) => r.item_number));
        const restantes = msg.chapterContext.filter(
          (c) => !citados.has(c.item_number)
        );
        if (!restantes.length) return null;
        return (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11, color: theme.subtext, marginBottom: 5 }}>
              Outros itens deste capítulo
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {restantes.map((c, i) => (
                <button key={i} onClick={() => setOpenSource(c)} style={{
                  background: 'transparent',
                  border: `1px solid ${theme.cardBorder}`,
                  color: theme.subtext, fontSize: 11,
                  padding: '3px 10px', borderRadius: 12,
                  cursor: 'pointer', fontWeight: 500,
                }}>
                  📖 {formatSourceRef({
                    book: c.book,
                    chapterRef: c.chapter_ref,
                    itemNumber: c.item_number,
                  })}
                </button>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Um voto na resposta. Este componente rende a resposta da IA tanto no
          chat quanto no estudo livre, então cobre os dois lugares de uma vez.
          Guardado por !isStreaming como os vizinhos: votar numa resposta que
          ainda está sendo escrita não faz sentido. */}
      {!isStreaming && <FeedbackButtons turnId={msg.turnId} theme={theme} />}

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
