import React, { useState } from 'react';
import { OBRAS } from '../../constants/obras';
import AIMessage from '../chat/AIMessage';
import UserBubble from '../chat/UserBubble';
import LoadingDots from '../chat/LoadingDots';

function DuvidaComposer({ theme, askingDuvida, setAskingDuvida, duvidaText, setDuvidaText, submitDuvida }) {
  return (
    <>
      <button onClick={() => setAskingDuvida(v => !v)} style={{
        background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
        color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
        fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
      }}>Tenho uma dúvida</button>
      {askingDuvida && (
        <div style={{ display: 'flex', gap: 6, width: '100%', maxWidth: 420, marginTop: 8 }}>
          <input
            value={duvidaText}
            onChange={e => setDuvidaText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); submitDuvida(); } }}
            placeholder="Digite sua dúvida…"
            autoFocus
            style={{
              flex: 1, background: theme.inputBg, border: `1px solid ${theme.inputBorder}`,
              borderRadius: 8, padding: '8px 12px', fontSize: 13.5, color: theme.text, outline: 'none',
            }}
          />
          <button onClick={submitDuvida} disabled={!duvidaText.trim()} style={{
            background: '#6B9BB8', color: 'white', border: 'none',
            padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
            cursor: duvidaText.trim() ? 'pointer' : 'not-allowed',
            opacity: duvidaText.trim() ? 1 : 0.5,
          }}>Perguntar</button>
        </div>
      )}
    </>
  );
}

/**
 * "Explorar Obras" free consultation mode.
 * Props:
 *   theme
 *   onBack               — () => void
 *   onRedirectDuvida     — (obraLabel) => void (unused by "Tenho uma dúvida"; see onAskDuvida)
 *   onAskDuvida          — (text) => void — submit inline follow-up question
 *   onAskTopic           — (query, obraId) => void  (triggers API call)
 *   messages             — array
 *   loading              — boolean
 *   onShare, onToggleFav, isFavorite
 *   fontSize
 */
export default function ExplorarObras({
  theme, onBack, onRedirectDuvida,
  onAskTopic, messages = [], loading,
  onShare, onToggleFav, isFavorite, fontSize,
  quickActions = [], onQuickAction,
  onBookChange, onAskDuvida,
}) {
  const [selectedObra, setSelectedObra] = useState('le');
  const [openParts, setOpenParts] = useState({});
  const obra = OBRAS.find(o => o.id === selectedObra) || OBRAS[0];
  const hasMessages = messages.length > 0;

  const [askingDuvida, setAskingDuvida] = useState(false);
  const [duvidaText, setDuvidaText] = useState('');

  const submitDuvida = () => {
    if (!duvidaText.trim()) return;
    onAskDuvida(duvidaText.trim());
    setDuvidaText('');
    setAskingDuvida(false);
  };

  const togglePart = (key) => setOpenParts(p => ({ ...p, [key]: !p[key] }));

  return (
    <>
      {/* Sticky header with obra selector */}
      <div style={{
        padding: '12px 18px 14px',
        borderBottom: `1px solid ${theme.headerBorder}`,
        flexShrink: 0, background: theme.headerBg,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <button onClick={onBack} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: theme.subtext, fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 3, padding: 0,
          }}>
            <svg width={10} height={10} viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            Estudar uma Obra
          </button>
          <span style={{ color: theme.subtext, fontSize: 12.5 }}>·</span>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: '#6B9BB8' }}>Explorar Obras</span>
        </div>

        {/* Obra card selector */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 7 }}>
          {OBRAS.map(o => {
            const active = o.id === selectedObra;
            return (
              <button key={o.id} onClick={() => {
                if (o.id !== selectedObra) onBookChange?.();
                setSelectedObra(o.id);
                setOpenParts({});
              }} style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
                padding: '8px 4px', borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${active ? '#6B9BB8' : 'rgba(107,155,184,.22)'}`,
                background: active ? 'rgba(107,155,184,.15)' : 'transparent',
                transition: 'all .15s',
              }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: active ? '#6B9BB8' : theme.subtext }}>{o.abbr}</div>
                <div style={{ fontSize: 11, lineHeight: 1.3, textAlign: 'center', color: active ? '#4A7A98' : theme.subtext }}>
                  {o.shortLabel}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Topics or messages */}
      {!hasMessages ? (
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '16px 18px' }}>
          <div style={{
            fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
            textTransform: 'uppercase', color: theme.subtext, marginBottom: 12,
          }}>Tópicos de {obra.label}</div>

          {obra.topics.map((part, i) => {
            const key = obra.id + '_' + i;
            const open = !!openParts[key];
            return (
              <div key={key} style={{
                marginBottom: 10, background: theme.cardBg,
                border: `1px solid ${theme.cardBorder}`, borderRadius: 8, overflow: 'hidden',
              }}>
                <div onClick={() => togglePart(key)} style={{
                  padding: '10px 14px', display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', cursor: 'pointer',
                }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: theme.text }}>{part.title}</div>
                    <div style={{ fontSize: 12, color: theme.subtext, marginTop: 2 }}>{part.subtitle}</div>
                  </div>
                  <svg width={13} height={13} viewBox="0 0 24 24" fill="none"
                    stroke={theme.subtext} strokeWidth="2" strokeLinecap="round"
                    style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform .2s' }}>
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </div>
                {open && (
                  <div style={{ borderTop: `1px solid ${theme.cardBorder}`, padding: '10px 14px' }}>
                    <div style={{ fontSize: 13, color: theme.subtext, lineHeight: 1.65, marginBottom: 10, fontStyle: 'italic' }}>
                      {part.context}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {part.items.map(item => (
                        <button key={item} onClick={() => onAskTopic(item, obra.id)} style={{
                          background: 'rgba(107,155,184,.07)', border: '1px solid rgba(107,155,184,.22)',
                          color: '#4A7A98', fontSize: 13, padding: '5px 12px',
                          borderRadius: 14, cursor: 'pointer', fontWeight: 500,
                        }}>{item}</button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Dúvida composer */}
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <DuvidaComposer theme={theme} askingDuvida={askingDuvida} setAskingDuvida={setAskingDuvida}
              duvidaText={duvidaText} setDuvidaText={setDuvidaText} submitDuvida={submitDuvida} />
          </div>
        </div>
      ) : (
        <div style={{
          flex: 1, overflowY: 'auto', minHeight: 0,
          padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 12,
        }}>
          {messages.map(msg => (
            msg.isUser
              ? <UserBubble key={msg.id} text={msg.text} />
              : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={fontSize}
                  showQuickActions={false}
                  quickActions={quickActions.filter(
                    qa => qa.label !== '📚 Relacionados' || msg.relatedItems?.length > 0
                  )}
                  onQuickAction={(label) => onQuickAction?.(label, msg)}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 10 }}>
                    <DuvidaComposer theme={theme} askingDuvida={askingDuvida} setAskingDuvida={setAskingDuvida}
                      duvidaText={duvidaText} setDuvidaText={setDuvidaText} submitDuvida={submitDuvida} />
                  </div>
                </AIMessage>
          ))}
          {loading && <LoadingDots theme={theme} />}
        </div>
      )}
    </>
  );
}
