// frontend/src/components/layout/HomeLauncher.jsx
import React from 'react';
import { MODES } from '../../constants/modes';
import { formatTrechoDate } from '../../utils/day';

/**
 * The default view (mode === null): the single canonical launcher.
 *
 * The "Nova conversa" dropdown is an acceleration of this screen, never an
 * alternative to it — if the dropdown became the primary path this screen would
 * go vestigial and the app would again have two competing launchers, which is
 * the problem this redesign exists to remove.
 *
 * The daily passage is the last card, in both layouts and with no isMobile
 * branch. It was in the sidebar, which was the last thing there that was not
 * material the reader had accumulated; moving it here is what finally makes the
 * sidebar history-only. Home is the opening screen of every session, so the
 * passage is still seen without being sought — the point of a daily reading —
 * and it keeps a short excerpt for the same reason: it should find the reader,
 * not merely be linkable.
 *
 * It carries no accent colour and sits in the same card language as the mode
 * cards above it (Estudar, Dialogar — Refletir is switched off for production,
 * see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md), because
 * it is the same kind of choice: what to do today.
 *
 * Contrast: `theme.subtext` measures 2.92:1 on the light background, below the
 * 4.5:1 WCAG AA floor. It is used here only for the card descriptions, which sit
 * beside a stronger label. Every line the reader must read on its own — the
 * subtitle, the passage excerpt — uses `theme.text`.
 */
export default function HomeLauncher({
  onPick, theme, isMobile = false, evangelhoData = null, onStudyTrecho,
}) {
  const trechoDate = formatTrechoDate(evangelhoData?.date);
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

        {/* Separated, but not promoted. The mode cards above answer the
            headline — "como você quer estudar" — and the passage is not a mode,
            it is a piece of content; rendered identically it read as a fourth
            mode. The rule marks the change of kind. It stays last because first
            position is a claim about priority: it would say the app is a daily
            devotional with study attached rather than the other way round, and
            would contradict the question printed directly above it. */}
        {onStudyTrecho && (
          <div style={{ height: 1, background: theme.cardBorder, margin: '10px 2px 2px' }} />
        )}

        {onStudyTrecho && (
          <button
            onClick={evangelhoData ? onStudyTrecho : undefined}
            disabled={!evangelhoData}
            style={{
              background: theme.cardBg,
              border: `1px solid ${theme.cardBorder}`,
              borderRadius: 12, padding: '16px 18px',
              cursor: evangelhoData ? 'pointer' : 'default',
              textAlign: 'left', display: 'flex', alignItems: 'flex-start', gap: 14,
              font: 'inherit', width: '100%',
              transition: 'background .15s, transform .1s',
            }}
          >
            <span style={{ fontSize: 26, flexShrink: 0, lineHeight: 1.1 }} aria-hidden="true">☀️</span>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={{
                display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8,
              }}>
                <span style={{
                  fontSize: 15.5, fontWeight: 600, color: theme.text,
                }}>Trecho do dia</span>
                {trechoDate && (
                  <span style={{ fontSize: 11.5, color: theme.subtext, flexShrink: 0 }}>
                    {trechoDate}
                  </span>
                )}
              </span>
              {evangelhoData ? (
                <span style={{
                  display: 'block',
                  fontFamily: "'Crimson Pro', serif", fontSize: 13.5, fontStyle: 'italic',
                  color: theme.text, lineHeight: 1.55, marginTop: 4,
                }}>"{evangelhoData.content.slice(0, isMobile ? 110 : 170)}…"</span>
              ) : (
                <span style={{
                  display: 'block', fontSize: 12.5, color: theme.subtext,
                  marginTop: 2, fontStyle: 'italic',
                }}>Carregando trecho do dia…</span>
              )}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
