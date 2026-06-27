import React, { useState } from 'react';
import { OBRAS } from '../../constants/obras';
import AIMessage from '../chat/AIMessage';
import UserBubble from '../chat/UserBubble';
import LoadingDots from '../chat/LoadingDots';

/**
 * "Explorar Obras" free consultation mode.
 * Props:
 *   theme
 *   onBack               — () => void
 *   onRedirectDuvida     — (obraLabel) => void
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
}) {
  const [selectedObra, setSelectedObra] = useState('le');
  const [openParts, setOpenParts] = useState({});
  const obra = OBRAS.find(o => o.id === selectedObra) || OBRAS[0];
  const hasMessages = messages.length > 0;

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
              <button key={o.id} onClick={() => { setSelectedObra(o.id); setOpenParts({}); }} style={{
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

          {/* Redirect prompt */}
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center' }}>
            <button onClick={() => onRedirectDuvida(obra.label)} style={{
              background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
              color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
              fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
            }}>Tenho uma dúvida</button>
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
                  onShare={() => onShare(msg)}
                  onToggleFav={() => onToggleFav(msg)}
                  isFavorite={isFavorite(msg.id)}
                  showQuickActions={false}
                >
                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
                    <button onClick={() => onRedirectDuvida(obra.label)} style={{
                      background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
                      color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
                      fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    }}>Tenho uma dúvida</button>
                  </div>
                </AIMessage>
          ))}
          {loading && <LoadingDots theme={theme} />}
        </div>
      )}
    </>
  );
}
