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
 *   completed      — boolean
 *   theme
 *   onNext         — () => void — advance to next step or complete
 *   onBack         — () => void — back to picker
 *   onRedirectDuvida — (msg) => void
 *   onShare        — (msg) => void
 *   onToggleFav    — (msg) => void
 *   isFavorite     — (id) => boolean
 *   fontSize       — string CSS value
 */
export default function GuidedStudy({
  trilha, currentStep, messages, loading, completed,
  theme, onNext, onBack, onRedirectDuvida, onShare, onToggleFav, isFavorite, fontSize,
}) {
  const scrollRef = useRef(null);
  const progress = trilha ? Math.round((currentStep / trilha.steps.length) * 100) : 0;
  const stepTitle = trilha?.steps[currentStep]?.label || '';
  const isLast = trilha && currentStep === trilha.steps.length - 1;
  const hasNext = trilha && currentStep < trilha.steps.length - 1;

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading]);

  // Find the last tutor message index (hasDaObra) for showing the next button
  const lastTutorIdx = messages.reduce((last, m, i) => m.isAI && m.hasDaObra ? i : last, -1);

  return (
    <>
      {/* Progress bar */}
      {!completed && (
        <div style={{ padding: '10px 18px 0', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button onClick={onBack} style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: theme.subtext, fontSize: 11, display: 'flex', alignItems: 'center', gap: 3, padding: 0,
              }}>
                <svg width={10} height={10} viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                  <polyline points="15 18 9 12 15 6"/>
                </svg>
                Trilhas
              </button>
              <span style={{ color: theme.subtext, fontSize: 11 }}>·</span>
              <span style={{ fontSize: 11, fontWeight: 500, color: theme.text }}>{stepTitle}</span>
            </div>
            <span style={{ fontSize: 10, color: theme.subtext }}>
              {currentStep + 1} de {trilha?.steps.length}
            </span>
          </div>
          <div style={{ height: 4, background: theme.cardBorder, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', background: '#6B9BB8', borderRadius: 2,
              width: `${progress}%`, transition: 'width .4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Completion */}
      {completed && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          padding: '40px 24px', animation: 'fade-up .4s ease',
        }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'rgba(107,155,184,.15)', border: '2px solid #6B9BB8',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 18, fontSize: 28,
          }}>✨</div>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 26, fontWeight: 600,
            color: theme.text, marginBottom: 8,
          }}>Trilha concluída!</div>
          <div style={{ fontSize: 13, color: theme.subtext, maxWidth: 300, lineHeight: 1.72, marginBottom: 8 }}>
            {trilha?.title}
          </div>
          <div style={{ fontSize: 12, color: theme.subtext, maxWidth: 320, lineHeight: 1.72, marginBottom: 28 }}>
            Você estudou os fundamentos da doutrina espírita. Continue explorando com as outras trilhas.
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            <button onClick={onBack} style={{
              background: '#6B9BB8', color: 'white', border: 'none',
              padding: '10px 22px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>Ver outras trilhas</button>
          </div>
        </div>
      )}

      {/* Messages */}
      {!completed && (
        <div ref={scrollRef} style={{
          flex: 1, overflowY: 'auto', minHeight: 0,
          padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 12,
        }}>
          {messages.map((msg, i) => (
            msg.isUser
              ? <UserBubble key={msg.id} text={msg.text} />
              : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={fontSize}
                  onShare={() => onShare(msg)}
                  onToggleFav={() => onToggleFav(msg)}
                  isFavorite={isFavorite(msg.id)}
                  showQuickActions={false}
                >
                  {/* Show next/duvida buttons only on last tutor message */}
                  {i === lastTutorIdx && (
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                      <button onClick={() => onRedirectDuvida(msg)} style={{
                        background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
                        color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
                        fontSize: 12, fontWeight: 500, cursor: 'pointer',
                      }}>Tenho uma dúvida</button>
                      {isLast
                        ? <button onClick={onNext} style={{
                            background: '#C8856A', color: 'white', border: 'none',
                            padding: '9px 22px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                          }}>Concluir trilha ✨</button>
                        : <button onClick={onNext} style={{
                            background: '#6B9BB8', color: 'white', border: 'none',
                            padding: '9px 22px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                          }}>Entendi, próximo →</button>
                      }
                    </div>
                  )}
                </AIMessage>
          ))}
          {loading && <LoadingDots theme={theme} />}
        </div>
      )}
    </>
  );
}
