import React, { useRef, useEffect } from 'react';
import AIMessage from '../chat/AIMessage';
import UserBubble from '../chat/UserBubble';
import LoadingDots from '../chat/LoadingDots';
import { useStickToBottom } from '../../hooks/useStickToBottom';

const FOLLOWUP_OPTIONS = [
  { icon: '💬', label: 'Explicar mais simples', build: (s) => `Explique de forma mais simples: "${s}"` },
  { icon: '🌱', label: 'Como aplicar', build: (s) => `Como posso aplicar isso no meu dia a dia? Contexto: "${s}"` },
];

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
 *   onAskDuvida    — (displayText, queryText) => void — submit contextualized follow-up
 *   fontSize       — string CSS value
 */
export default function GuidedStudy({
  trilha, currentStep, messages, loading,
  theme, onNext, onBack, onAskDuvida, fontSize,
  quickActions = [], onQuickAction,
}) {
  const scrollRef = useRef(null);
  const attachScroll = useStickToBottom(scrollRef); // follow the reveal
  const progress = trilha ? Math.round(((currentStep + 1) / trilha.steps.length) * 100) : 0;
  const stepTitle = trilha?.steps[currentStep]?.label || '';
  const isLast = trilha && currentStep === trilha.steps.length - 1;

  // Jump to the bottom when a message is added / loading toggles; the pin
  // above then keeps us there as the answer reveals word by word.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Last AI message (any) — where "Entendi →" lives
  const lastAiIdx = messages.reduce((last, m, i) => m.isAI ? i : last, -1);
  // Last step card — source of the snippet for follow-up queries
  const lastStepMsg = [...messages].reverse().find(m => m.isAI && m.hasDaObra);
  const snippet = (lastStepMsg?.obra?.quote || lastStepMsg?.ia || '').slice(0, 400);
  // Whether the last AI message is still the step card (no follow-up sent yet)
  const lastAiIsStep = messages[lastAiIdx]?.hasDaObra;

  const btnBase = {
    border: 'none', padding: '9px 22px', borderRadius: 8,
    fontSize: 14.5, fontWeight: 600,
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.45 : 1,
  };

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
      <div ref={attachScroll} style={{
        flex: 1, overflowY: 'auto', minHeight: 0,
        padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {messages.map((msg, i) => (
          msg.isUser
            ? <div key={msg.id}><UserBubble text={msg.text} /></div>
            : <div key={msg.id}>
              <AIMessage msg={msg} theme={theme} fontSize={fontSize}
                showQuickActions={false}
                quickActions={quickActions.filter(
                  qa => qa.label !== '📚 Relacionados' || msg.relatedItems?.length > 0
                )}
                onQuickAction={(label) => onQuickAction?.(label, msg)}
              >
                {i === lastAiIdx && (
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginTop: 12 }}>
                    {/* Follow-up buttons only while still on the step card */}
                    {lastAiIsStep && FOLLOWUP_OPTIONS.map(opt => (
                      <button
                        key={opt.label}
                        disabled={loading}
                        onClick={() => onAskDuvida(opt.label, opt.build(snippet))}
                        style={{
                          background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
                          color: '#4A7A98', padding: '9px 16px', borderRadius: 8,
                          fontSize: 13.5, fontWeight: 500,
                          cursor: loading ? 'not-allowed' : 'pointer',
                          opacity: loading ? 0.45 : 1,
                          display: 'flex', alignItems: 'center', gap: 6,
                        }}
                      >
                        <span>{opt.icon}</span>{opt.label}
                      </button>
                    ))}
                    {isLast
                      ? <button onClick={onNext} disabled={loading} style={{ ...btnBase, background: '#C8856A', color: 'white' }}>
                          Concluir trilha ✨
                        </button>
                      : <button onClick={onNext} disabled={loading} style={{ ...btnBase, background: '#6B9BB8', color: 'white' }}>
                          Entendi, próximo ›
                        </button>
                    }
                  </div>
                )}
              </AIMessage>
            </div>
        ))}
        {loading && <LoadingDots theme={theme} />}
      </div>
    </>
  );
}
