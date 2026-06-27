import React from 'react';
import ObraBlock from './ObraBlock';
import IABlock from './IABlock';

const BookIcon = ({ size = 11, color = 'white' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);

/**
 * Full AI response: avatar + ObraBlock (if hasDaObra) + IABlock.
 * Pass showQuickActions=false in guided/free study modes.
 */
export default function AIMessage({
  msg, theme, fontSize,
  onShare, onToggleFav, isFavorite,
  showQuickActions = true,
  quickActions = [],
  children, // optional slot for buttons below (e.g. "Entendi, próximo →")
}) {
  return (
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', animation: 'fade-up .3s ease' }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', background: '#6B9BB8',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, marginTop: 2,
      }}>
        <BookIcon />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {msg.hasDaObra && <ObraBlock obra={msg.obra} theme={theme} />}
        <IABlock
          msg={msg} theme={theme} fontSize={fontSize}
          onShare={onShare} onToggleFav={onToggleFav} isFavorite={isFavorite}
          showQuickActions={showQuickActions} quickActions={quickActions}
        />
        {children}
      </div>
    </div>
  );
}
