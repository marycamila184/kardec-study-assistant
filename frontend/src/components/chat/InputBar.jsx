import React, { useRef, useEffect, useState } from 'react';

const InfoIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <line x1="12" y1="8" x2="12" y2="8.01"/>
    <line x1="12" y1="12" x2="12" y2="16"/>
  </svg>
);

/**
 * Sticky input bar at the bottom of the chat.
 * @prop {string}   value        Controlled textarea value
 * @prop {function} onChange     Called with new string value
 * @prop {function} onSend       Called when user sends
 * @prop {string}   placeholder
 * @prop {string}   footerHint   Small text below input (desktop) / tooltip (mobile)
 * @prop {object}   theme
 * @prop {boolean}  loading      Disables input/send while a request is in flight
 * @prop {boolean}  isMobile     Switches hint to info-icon tooltip
 */
export default function InputBar({ value, onChange, onSend, placeholder, footerHint, theme, loading = false, isMobile = false }) {
  const ref = useRef(null);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => { if (ref.current && !loading) ref.current.focus(); }, [placeholder, loading]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading) onSend();
    }
  };

  const canSend = !loading && value.trim().length > 0;

  return (
    <div style={{
      padding: '10px 16px 14px',
      borderTop: `1px solid ${theme.headerBorder}`,
      flexShrink: 0, background: theme.headerBg,
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <textarea
          ref={ref}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={1}
          disabled={loading}
          aria-label="Digite sua mensagem"
          aria-busy={loading}
          style={{
            flex: 1, background: theme.inputBg,
            border: `1px solid ${theme.inputBorder}`,
            borderRadius: 10, padding: '9px 13px',
            fontSize: 15, color: theme.text, lineHeight: 1.55,
            resize: 'none', fontFamily: 'inherit', overflowY: 'hidden',
            outline: 'none', opacity: loading ? 0.6 : 1,
          }}
        />
        {isMobile && footerHint && (
          <div style={{ position: 'relative', flexShrink: 0, alignSelf: 'flex-end', marginBottom: 1 }}>
            <button
              onClick={() => setShowTooltip(v => !v)}
              aria-label="Sobre este assistente"
              style={{
                width: 36, height: 36, background: 'transparent',
                border: `1px solid ${theme.inputBorder}`,
                borderRadius: 10, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: theme.subtext,
              }}
            >
              <InfoIcon />
            </button>
            {showTooltip && (
              <>
                <div
                  style={{ position: 'fixed', inset: 0, zIndex: 98 }}
                  onClick={() => setShowTooltip(false)}
                />
                <div style={{
                  position: 'absolute', bottom: 44, right: 0,
                  zIndex: 99, width: 230,
                  background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                  borderRadius: 10, padding: '10px 13px',
                  boxShadow: '0 4px 18px rgba(0,0,0,.18)',
                  fontSize: 12.5, color: theme.text, lineHeight: 1.65,
                }}>
                  {footerHint.split(' · ').filter(p => !p.toLowerCase().includes('enter')).map((part, i, arr) => (
                    <span key={i}>
                      {part}{i < arr.length - 1 && <br/>}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        <button
          onClick={onSend}
          disabled={!canSend}
          aria-label="Enviar mensagem"
          style={{
            width: 36, height: 36, background: '#6B9BB8', border: 'none',
            borderRadius: 10, cursor: canSend ? 'pointer' : 'not-allowed',
            opacity: canSend ? 1 : 0.5,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
            stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2" fill="white" stroke="none"/>
          </svg>
        </button>
      </div>
      {!isMobile && footerHint && (
        <div style={{ fontSize: 11, color: theme.subtext, marginTop: 5 }}>{footerHint}</div>
      )}
    </div>
  );
}
