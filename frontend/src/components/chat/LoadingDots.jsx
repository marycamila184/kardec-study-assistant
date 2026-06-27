import React from 'react';

export default function LoadingDots({ theme }) {
  const dotStyle = {
    width: 6, height: 6, borderRadius: '50%',
    background: '#C8856A', display: 'inline-block',
  };
  return (
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', background: '#6B9BB8',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2,
      }}>
        <BookIcon size={11} color="white" />
      </div>
      <div style={{
        background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
        borderRadius: 10, padding: '12px 16px', display: 'flex', gap: 5, alignItems: 'center', marginTop: 2,
      }}>
        <div style={{ ...dotStyle, animation: 'dot-pulse 1.2s infinite 0s' }} />
        <div style={{ ...dotStyle, animation: 'dot-pulse 1.2s infinite 0.22s' }} />
        <div style={{ ...dotStyle, animation: 'dot-pulse 1.2s infinite 0.44s' }} />
      </div>
    </div>
  );
}

function BookIcon({ size = 14, color = 'white' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
    </svg>
  );
}
