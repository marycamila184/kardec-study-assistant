import React, { useRef, useEffect } from 'react';
import AIMessage from '../chat/AIMessage';
import UserBubble from '../chat/UserBubble';
import LoadingDots from '../chat/LoadingDots';

/**
 * Guided trilha study mode.
 * Props:
 *   trilha         — trilha object from TRILHAS
 *   currentStep    — number (0-indexed)
 *   messages       — array of {id, isUser, isAI, text?, hasDaObra?, obra?, ia?}
 *   loading        — boolean
 *   theme
 *   onNext         — () => void — advance to next step, or complete the trilha and navigate back
 *   onBack         — () => void — back to picker
 *   onRedirectDuvida — (msg) => void
 *   onShare        — (msg) => void
 *   onToggleFav    — (msg) => void
 *   isFavorite     — (id) => boolean
 *   fontSize       — string CSS value
 */
export default function GuidedStudy({
  trilha, currentStep, messages, loading,
  theme, onNext, onBack, onRedirectDuvida, onShare, onToggleFav, isFavorite, fontSize,
  quickActions = [], onQuickAction,
}) {
  const scrollRef = useRef(null);
  const progress = trilha ? Math.round(((currentStep + 1) / trilha.steps.length) * 100) : 0;
  const stepTitle = trilha?.steps[currentStep]?.label || '';
  const isLast = trilha && currentStep === trilha.steps.length - 1;

  useEffect(() => {
    let ticks = 0;
    const interval = setInterval(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      ticks += 1;
      if (ticks >= 20) clearInterval(interval); // ~2s at 100ms
    }, 100);
    return () => clearInterval(interval);
  }, [messages, loading]);

  // Find the last tutor message index (hasDaObra) for showing the next button
  const lastTutorIdx = messages.reduce((last, m, i) => m.isAI && m.hasDaObra ? i : last, -1);

  return (
    <>
      {/* Progress bar */}
      <div style={{ padding: '10px 18px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button onClick={onBack} style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: theme.subtext, fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 3, padding: 0,
            }}>
              <svg width={10} height={10} viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <polyline points="15 18 9 12 15 6"/>
              </svg>
              Trilhas
            </button>
            <span style={{ color: theme.subtext, fontSize: 12.5 }}>·</span>
            <span style={{ fontSize: 12.5, fontWeight: 500, color: theme.text }}>{stepTitle}</span>
          </div>
          <span style={{ fontSize: 12, color: theme.subtext }}>
            {currentStep + 1} de {trilha?.steps.length}
          </span>
        </div>
        <div style={{ height: 4, background: theme.cardBorder, borderRadius: 2, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: progress >= 100 ? '#4CAF50' : '#6B9BB8', borderRadius: 2,
            width: `${progress}%`, transition: 'width .4s ease, background .3s ease',
          }} />
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', minHeight: 0,
        padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {messages.map((msg, i) => (
          msg.isUser
            ? <UserBubble key={msg.id} text={msg.text} />
            : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={fontSize}
                showQuickActions={false}
                quickActions={quickActions.filter(
                  qa => qa.label !== '📚 Relacionados' || msg.relatedItems?.length > 0
                )}
                onQuickAction={(label) => onQuickAction?.(label, msg)}
              >
                {/* Show next/duvida buttons only on last tutor message */}
                {i === lastTutorIdx && (
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                    <button onClick={() => onRedirectDuvida(msg)} disabled={loading} style={{
                      background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
                      color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
                      fontSize: 13.5, fontWeight: 500,
                      cursor: loading ? 'not-allowed' : 'pointer',
                      opacity: loading ? 0.45 : 1,
                    }}>Tenho uma dúvida</button>
                    {isLast
                      ? <button onClick={onNext} disabled={loading} style={{
                          background: '#C8856A', color: 'white', border: 'none',
                          padding: '9px 22px', borderRadius: 8, fontSize: 14.5, fontWeight: 600,
                          cursor: loading ? 'not-allowed' : 'pointer',
                          opacity: loading ? 0.45 : 1,
                        }}>Concluir trilha ✨</button>
                      : <button onClick={onNext} disabled={loading} style={{
                          background: '#6B9BB8', color: 'white', border: 'none',
                          padding: '9px 22px', borderRadius: 8, fontSize: 14.5, fontWeight: 600,
                          cursor: loading ? 'not-allowed' : 'pointer',
                          opacity: loading ? 0.45 : 1,
                        }}>Entendi, próximo →</button>
                    }
                  </div>
                )}
              </AIMessage>
        ))}
        {loading && <LoadingDots theme={theme} />}
      </div>
    </>
  );
}
