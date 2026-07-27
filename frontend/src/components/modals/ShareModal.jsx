import React from 'react';
import { useEscapeKey } from '../../hooks/useEscapeKey';

const WhatsAppIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
  </svg>
);

/**
 * Share quote modal — shows preview card + copy/WhatsApp/download actions.
 */
export default function ShareModal({ msg, theme, onClose, isMobile = false }) {
  useEscapeKey(onClose, !!msg);
  if (!msg) return null;

  const quote    = msg.obra?.quote    || msg.fullText || msg.ia?.slice(0, 500) || '';
  const citation = msg.obra?.citation || 'Dialogando com a Doutrina';
  const context  = msg.obra?.context  || '';

  const shareText = `"${quote}"\n\n— ${citation}\n\nDialogando com a Doutrina`;

  const handleWhatsApp = () => {
    const url = `https://wa.me/?text=${encodeURIComponent(shareText)}`;
    window.open(url, '_blank', 'noopener');
  };

  // Testa com um arquivo de verdade, não só a existência da função: o Chrome do
  // desktop tem navigator.canShare mas recusa arquivos, então checar só o
  // `typeof` fazia o botão prometer "Compartilhar imagem" e baixar.
  const canShareFile = (() => {
    if (typeof navigator === 'undefined' || typeof navigator.canShare !== 'function') {
      return false;
    }
    try {
      return navigator.canShare({
        files: [new File([new Blob()], 'x.png', { type: 'image/png' })],
      });
    } catch {
      return false;
    }
  })();

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
    // Entrega da imagem, em três degraus.
    //
    // O caminho antigo era `link.download` + data URL, e ele simplesmente não
    // funciona no celular: o Safari do iOS ignora o atributo download, e a data
    // URL abre na mesma aba ou não faz nada — o botão parecia morto.
    //
    // 1. navigator.share com arquivo: abre a folha de compartilhamento do
    //    sistema, que é o que "compartilhar" significa num telefone.
    // 2. download via blob URL: desktop, onde o atributo download é respeitado.
    // 3. abrir numa aba: último recurso, a pessoa segura o dedo e salva.
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const file = new File([blob], 'trecho-espirita.png', { type: 'image/png' });

      if (navigator.canShare?.({ files: [file] })) {
        try {
          // Imagem E texto no mesmo envio: quem escolher WhatsApp recebe a foto
          // com a legenda, em vez de ter de decidir antes entre um e outro.
          await navigator.share({ files: [file], text: shareText });
          return;
        } catch (err) {
          // Cancelar a folha de compartilhamento levanta AbortError. Não é
          // falha: cair no download depois disso reabriria algo que a pessoa
          // acabou de fechar.
          if (err?.name === 'AbortError') return;
        }
      }

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.download = 'trecho-espirita.png';
      link.href = url;
      if ('download' in link) {
        link.click();
      } else {
        window.open(url, '_blank', 'noopener');
      }
      // Revoga depois do clique: revogar imediatamente cancela o download em
      // alguns navegadores.
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }, 'image/png');
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: isMobile ? 12 : 24, background: 'rgba(0,0,0,.5)',
    }} onClick={onClose}>
      {/* O trecho do dia pode ser longo, e sem teto de altura o cartão crescia
          para fora da tela no celular: o rodapé com os botões ficava abaixo da
          dobra, sem rolagem, e a pessoa via um cartão cortado sem saída.
          maxHeight prende o modal na viewport e a rolagem vai para o miolo,
          deixando cabeçalho e ações sempre visíveis. */}
      <div style={{
        background: theme.headerBg, borderRadius: 14,
        maxWidth: 480, width: '100%', maxHeight: '92vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 48px rgba(0,0,0,.3)', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '16px 18px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>Compartilhar trecho</div>
          <button onClick={onClose} aria-label="Fechar" style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 20, color: theme.subtext, padding: '0 4px', lineHeight: 1,
          }}>×</button>
        </div>

        {/* Preview card */}
        <div style={{
          background: 'linear-gradient(135deg, #3A6E8A, #2A5070)',
          padding: isMobile ? '22px 20px' : '32px 28px',
          overflowY: 'auto', minHeight: 0,
        }}>
          <div style={{
            fontSize: 8.5, fontWeight: 700, letterSpacing: '.18em',
            textTransform: 'uppercase', color: 'rgba(255,255,255,.5)', marginBottom: 18,
          }}>Dialogando com a Doutrina</div>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: isMobile ? 17 : 20, fontStyle: 'italic',
            color: 'white', lineHeight: 1.7, marginBottom: 16,
            overflowWrap: 'anywhere',
          }}>{quote}</div>
          <div style={{ height: 1, background: 'rgba(255,255,255,.2)', marginBottom: 14 }} />
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,.65)' }}>{citation}</div>
          {context && (
            <div style={{ fontSize: 8, color: 'rgba(255,255,255,.35)', marginTop: 6 }}>{context}</div>
          )}
        </div>

        {/* Ações.

            Onde existe folha do sistema, um botão só. Dois botões confundiam:
            o verde tinha a marca do WhatsApp e mandava apenas texto, enquanto o
            de imagem — que é o que a pessoa quer compartilhar — parecia
            secundário. A folha já lista WhatsApp, Instagram e o que mais
            estiver instalado, e agora leva foto e legenda juntas.

            No desktop os dois continuam, porque lá não há folha: o WhatsApp Web
            abre com o texto e o outro salva o arquivo. */}
        <div style={{ padding: '14px 18px', display: 'flex', gap: 8, flexShrink: 0 }}>
          {!canShareFile && (
            <button onClick={handleWhatsApp} style={{
              flex: 1, background: '#25D366', border: 'none',
              color: 'white', fontSize: 12, fontWeight: 600, padding: 9, borderRadius: 7,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              <WhatsAppIcon /> WhatsApp
            </button>
          )}
          <button onClick={handleDownload} style={{
            flex: 1, background: '#6B9BB8', border: 'none',
            color: 'white', fontSize: 12, fontWeight: 500, padding: 9, borderRadius: 7, cursor: 'pointer',
          }}>{canShareFile ? 'Compartilhar' : 'Baixar imagem'}</button>
        </div>
      </div>
    </div>
  );
}
