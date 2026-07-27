import React from 'react';

/**
 * "———  Hoje  ———" between the messages of different days.
 *
 * Quiet by design: it is a wayfinding mark, not content. It uses theme.subtext,
 * which fails the 4.5:1 contrast floor for body copy — acceptable here only
 * because the label is decorative and the thread reads correctly without it.
 */
export default function DayDivider({ label, theme }) {
  if (!label) return null;
  return (
    <div
      role="separator"
      aria-label={label}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        margin: '6px 0 2px',
      }}
    >
      <div style={{ flex: 1, height: 1, background: theme.cardBorder }} />
      <span style={{
        fontSize: 10.5, fontWeight: 600, letterSpacing: '.06em',
        textTransform: 'uppercase', color: theme.subtext, whiteSpace: 'nowrap',
      }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: theme.cardBorder }} />
    </div>
  );
}
