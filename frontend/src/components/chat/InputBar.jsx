import React, { useRef, useEffect } from 'react';

/**
 * Sticky input bar at the bottom of the chat.
 * @prop {string}   value        Controlled textarea value
 * @prop {function} onChange     Called with new string value
 * @prop {function} onSend       Called when user sends
 * @prop {string}   placeholder
 * @prop {string}   footerHint   Small text below input
 * @prop {object}   theme
 */
export default function InputBar({ value, onChange, onSend, placeholder, footerHint, theme }) {
  const ref = useRef(null);

  // Auto-focus & auto-resize
  useEffect(() => { if (ref.current) ref.current.focus(); }, [placeholder]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };

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
          style={{
            flex: 1, background: theme.inputBg,
            border: `1px solid ${theme.inputBorder}`,
            borderRadius: 10, padding: '9px 13px',
            fontSize: 15, color: theme.text, lineHeight: 1.55,
            resize: 'none', fontFamily: 'inherit', overflowY: 'hidden',
            outline: 'none',
          }}
        />
        <button onClick={onSend} style={{
          width: 36, height: 36, background: '#6B9BB8', border: 'none',
          borderRadius: 10, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
            stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2" fill="white" stroke="none"/>
          </svg>
        </button>
      </div>
      {footerHint && (
        <div style={{ fontSize: 11, color: theme.subtext, marginTop: 5 }}>{footerHint}</div>
      )}
    </div>
  );
}
