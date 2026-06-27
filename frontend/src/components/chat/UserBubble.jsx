import React from 'react';

export default function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', animation: 'fade-up .25s ease' }}>
      <div style={{
        background: '#6B9BB8', color: 'white',
        padding: '10px 14px',
        borderRadius: '16px 16px 4px 16px',
        maxWidth: '66%', fontSize: 15, lineHeight: 1.6, wordBreak: 'break-word',
      }}>
        {text}
      </div>
    </div>
  );
}
