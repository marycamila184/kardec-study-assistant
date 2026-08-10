// frontend/src/components/layout/TrechoCard.jsx
import React from 'react';
import { formatTrechoDate } from '../../utils/day';

/**
 * The daily-passage card.
 *
 * Extracted from HomeLauncher so the home screen and the empty Dialogar screen
 * render one card, not two that look alike. This repo already paid for that
 * lesson once: `constants/modes.js` exists because the home cards and the
 * "Nova conversa" dropdown had to be prevented from drifting apart.
 *
 * It knows nothing about where it sits. The divider that separates it from
 * whatever is above belongs to the caller — the two call sites want different
 * spacing, and a `dividerMargin` prop would be a prop whose only job is to undo
 * the abstraction.
 *
 * `excerptChars` has no default on purpose. Home shows 170 on desktop and 110
 * on mobile; the chat screen shows 75, because it also carries a heading, a
 * description, three wrapping chips and the input bar. A default here would be
 * a fourth opinion that no screen asked for.
 *
 * The card has three states, and the third one exists because of a bug: with
 * `evangelhoData` null it said "Carregando trecho do dia…" forever, whether the
 * answer was still in flight or was never coming. Measured on 2026-08-10, a
 * blocked /evangelho (CORS, backend down, no network — the client cannot tell
 * them apart) looked exactly like a slow one, and the person debugging it
 * started in the wrong place. `evangelhoFailed` splits "not yet" from "not
 * going to", and the card says which.
 */
export default function TrechoCard({
  theme, evangelhoData, evangelhoFailed = false, onStudyTrecho, excerptChars,
}) {
  const trechoDate = formatTrechoDate(evangelhoData?.date);
  return (
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
          }}>"{evangelhoData.content.slice(0, excerptChars)}…"</span>
        ) : (
          <span style={{
            display: 'block', fontSize: 12.5, color: theme.subtext,
            marginTop: 2, fontStyle: 'italic',
          }}>
            {evangelhoFailed
              ? 'Não foi possível carregar o trecho de hoje.'
              : 'Carregando trecho do dia…'}
          </span>
        )}
      </span>
    </button>
  );
}
