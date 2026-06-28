import React, { useState } from 'react';

/**
 * Share quote modal — shows preview card + copy/download actions.
 * Props:
 *   msg    — { obra: { quote, citation, context } }
 *   theme
 *   onClose — () => void
 */
export default function ShareModal({ msg, theme, onClose }) {
  const [copied, setCopied] = useState(false);

  if (!msg) return null;

  const quote    = msg.obra?.quote    || msg.ia?.slice(0, 500) || '';
  const citation = msg.obra?.citation || 'Dialogando com a Doutrina';
  const context  = msg.obra?.context  || '';

  const handleCopy = async () => {
    const text = `${quote}\n\n— ${citation}\n\nDialogando com a Doutrina`;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 960; canvas.height = 560;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 960, 560);
    grad.addColorStop(0, '#3A6E8A'); grad.addColorStop(1, '#2A5070');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 960, 560);
    ctx.fillStyle = 'rgba(255,255,255,.45)';
    ctx.font = '500 13px DM Sans, sans-serif';
    ctx.fillText('DIALOGANDO COM A DOUTRINA', 52, 58);
    ctx.fillStyle = 'white';
    ctx.font = 'italic 300 28px Crimson Pro, Georgia, serif';
    const words = quote.replace(/"/g, '').split(' ');
    let line = '', y = 110;
    for (const w of words) {
      const test = line + w + ' ';
      if (ctx.measureText(test).width > 856 && line) {
        ctx.fillText(line.trim(), 52, y); line = w + ' '; y += 44;
        if (y > 460) { ctx.fillText('…', 52, y); break; }
      } else { line = test; }
    }
    if (y <= 460) ctx.fillText(line.trim(), 52, y);
    ctx.strokeStyle = 'rgba(255,255,255,.2)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(52, y + 24); ctx.lineTo(908, y + 24); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,.6)';
    ctx.font = '13px DM Sans, sans-serif';
    ctx.fillText(citation, 52, y + 50);
    const link = document.createElement('a');
    link.download = 'trecho-espirita.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: 'rgba(0,0,0,.5)',
    }}>
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 480, width: '100%', boxShadow: '0 8px 48px rgba(0,0,0,.3)', overflow: 'hidden',
      }}>
        <div style={{
          padding: '16px 18px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Compartilhar trecho</div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 20, color: theme.subtext, padding: '0 4px', lineHeight: 1,
          }}>×</button>
        </div>

        {/* Preview card */}
        <div style={{
          background: 'linear-gradient(135deg, #3A6E8A, #2A5070)',
          padding: '32px 28px',
        }}>
          <div style={{
            fontSize: 8.5, fontWeight: 700, letterSpacing: '.18em',
            textTransform: 'uppercase', color: 'rgba(255,255,255,.5)', marginBottom: 18,
          }}>Dialogando com a Doutrina</div>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 20, fontStyle: 'italic',
            color: 'white', lineHeight: 1.7, marginBottom: 16,
          }}>{quote}</div>
          <div style={{ height: 1, background: 'rgba(255,255,255,.2)', marginBottom: 14 }} />
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,.65)' }}>{citation}</div>
          {context && (
            <div style={{ fontSize: 8, color: 'rgba(255,255,255,.35)', marginTop: 6 }}>{context}</div>
          )}
        </div>

        {/* Actions */}
        <div style={{ padding: '14px 18px', display: 'flex', gap: 8 }}>
          <button onClick={handleCopy} style={{
            flex: 1, background: 'rgba(107,155,184,.1)',
            border: '1px solid rgba(107,155,184,.3)',
            color: '#4A7A98', fontSize: 12, fontWeight: 500, padding: 9, borderRadius: 7, cursor: 'pointer',
          }}>{copied ? '✓ Copiado!' : 'Copiar texto'}</button>
          <button onClick={handleDownload} style={{
            flex: 1, background: '#6B9BB8', border: 'none',
            color: 'white', fontSize: 12, fontWeight: 500, padding: 9, borderRadius: 7, cursor: 'pointer',
          }}>Baixar imagem</button>
        </div>
      </div>
    </div>
  );
}
