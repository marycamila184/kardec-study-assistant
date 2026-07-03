import React, { useState } from 'react';

const OPTIONS = [
  { label: '💬 Explique de forma mais simples', build: (s) => `Explique de forma mais simples: "${s}"` },
  { label: '💡 Dê um exemplo prático', build: (s) => `Dê um exemplo prático relacionado a: "${s}"` },
  { label: '📅 Como aplicar no dia a dia?', build: (s) => `Como posso aplicar isso no meu dia a dia? Contexto: "${s}"` },
];

/**
 * "Tenho uma dúvida" follow-up affordance for Guided Study / Explorar Obras.
 * Replaces free-text input with preset buttons that build a contextualized
 * query from the current passage, so /chat has something real to retrieve
 * against instead of a bare, ambiguous phrase.
 * Props:
 *   theme
 *   snippet  — string, the current passage/answer text to build queries from
 *   onAsk    — (displayText: string, queryText: string) => void
 *   loading  — boolean
 */
export default function FollowUpButtons({ theme, snippet, onAsk, loading }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button onClick={() => setOpen(v => !v)} disabled={loading} style={{
        background: 'transparent', border: '1px solid rgba(107,155,184,.4)',
        color: '#4A7A98', padding: '9px 18px', borderRadius: 8,
        fontSize: 13.5, fontWeight: 500,
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.45 : 1,
      }}>Tenho uma dúvida</button>
      {open && (
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 6, width: '100%', maxWidth: 420,
          marginTop: 8, justifyContent: 'center',
        }}>
          {OPTIONS.map(opt => (
            <button
              key={opt.label}
              disabled={loading}
              onClick={() => { onAsk(opt.label, opt.build(snippet)); setOpen(false); }}
              style={{
                background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                color: theme.text, padding: '8px 14px', borderRadius: 8,
                fontSize: 13, fontWeight: 500,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
              }}
            >{opt.label}</button>
          ))}
        </div>
      )}
    </>
  );
}
