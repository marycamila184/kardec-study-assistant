// frontend/src/components/layout/HomeLauncher.jsx
import React from 'react';
import { MODES } from '../../constants/modes';

/**
 * The default view (mode === null): the single canonical launcher.
 *
 * The "Nova conversa" dropdown is an acceleration of this screen, never an
 * alternative to it — if the dropdown became the primary path this screen would
 * go vestigial and the app would again have two competing launchers, which is
 * the problem this redesign exists to remove.
 *
 * The daily passage appears here as well as in the sidebar: on mobile the
 * sidebar is a drawer, so without this card the passage would cost two taps.
 *
 * Contrast: `theme.subtext` measures 2.92:1 on the light background, below the
 * 4.5:1 WCAG AA floor. It is used here only for the card descriptions, which sit
 * beside a stronger label. Every line the reader must actually read on its own —
 * the subtitle, the trecho button — uses `theme.text`.
 */
export default function HomeLauncher({ onPick, theme, evangelhoData, onStudyTrecho, isMobile = false }) {
  return (
    <div style={{
      flex: 1, overflowY: 'auto', minHeight: 0,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: isMobile ? '32px 18px' : '48px 24px',
    }}>
      <h1 style={{
        fontFamily: "'Crimson Pro', serif",
        fontSize: isMobile ? 24 : 30, fontWeight: 600, color: theme.text,
        margin: 0, textAlign: 'center', lineHeight: 1.25,
      }}>
        Como você quer estudar hoje?
      </h1>
      <p style={{
        fontSize: 13.5, color: theme.text, margin: '10px 0 30px',
        textAlign: 'center', maxWidth: 460, lineHeight: 1.5,
      }}>
        Escolha um caminho para começar. Toda conversa fica salva no histórico.
      </p>

      <div style={{
        display: 'flex', flexDirection: 'column', gap: 12,
        width: '100%', maxWidth: 420,
      }}>
        {MODES.map(m => (
          <button
            key={m.id}
            onClick={() => onPick(m.id)}
            style={{
              background: theme.cardBg,
              border: `1px solid ${theme.cardBorder}`,
              borderRadius: 12, padding: '16px 18px', cursor: 'pointer',
              textAlign: 'left', display: 'flex', alignItems: 'center', gap: 14,
              font: 'inherit', width: '100%',
              transition: 'background .15s, transform .1s',
            }}
          >
            <span style={{ fontSize: 26, flexShrink: 0 }}>{m.icon}</span>
            <span style={{ minWidth: 0 }}>
              <span style={{
                display: 'block', fontSize: 15.5, fontWeight: 600, color: theme.text,
              }}>{m.label}</span>
              <span style={{
                display: 'block', fontSize: 12.5, color: theme.subtext, marginTop: 2, lineHeight: 1.4,
              }}>{m.desc}</span>
            </span>
          </button>
        ))}
      </div>

      {evangelhoData && (
        <button
          onClick={onStudyTrecho}
          style={{
            marginTop: 26, background: 'transparent',
            border: `1px solid ${theme.cardBorder}`, borderRadius: 999,
            padding: '9px 18px', cursor: 'pointer', font: 'inherit',
            fontSize: 12.5, color: theme.text,
            display: 'flex', alignItems: 'center', gap: 7,
          }}
        >
          ☀️ Ler o trecho do dia
        </button>
      )}
    </div>
  );
}
