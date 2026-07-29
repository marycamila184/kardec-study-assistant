import { useState } from 'react';
import { hasAnswered, grantConsent, revokeConsent } from '../../services/consent';

// Opt-in específico, não um aviso de cookies. O que se registra aqui é
// convicção religiosa e, às vezes, relato de sofrimento — dado sensível, para o
// qual "continuar usando implica aceitação" não é consentimento válido.
//
// Os dois botões têm o mesmo peso visual de propósito: um "recusar" apagado ao
// lado de um "aceitar" destacado descaracteriza o consentimento livre, que é a
// base legal inteira em que isto se apoia. Se alguém for mexer no visual daqui,
// é esta a linha que não pode ser cruzada.
//
// Aparece uma vez: respondido, a escolha fica em localStorage e ele não volta.
// Quem quiser mudar de ideia vai em Configurações → Privacidade.
//
// Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
export default function ConsentBanner({ theme }) {
  const [dismissed, setDismissed] = useState(hasAnswered);
  if (dismissed) return null;

  const decide = (fn) => () => {
    fn();
    setDismissed(true);
  };

  const button = {
    flex: 1,
    padding: '9px 14px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    border: `1px solid ${theme.cardBorder}`,
    background: 'transparent',
    color: theme.text,
    fontFamily: 'inherit',
  };

  return (
    <div
      role="dialog"
      aria-label="Consentimento para registro de conversas"
      style={{
        position: 'fixed', bottom: 12, left: 12, right: 12, zIndex: 1000,
        maxWidth: 460, margin: '0 auto', padding: 16, borderRadius: 12,
        background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
        boxShadow: '0 4px 18px rgba(0,0,0,.10)',
      }}
    >
      <p style={{ fontSize: 13, lineHeight: 1.65, color: theme.text, margin: '0 0 10px' }}>
        Posso guardar nossas conversas, sem identificar você, para ir
        melhorando as respostas?
      </p>
      {/* O detalhe todo — o que é guardado, por quanto tempo, o que nunca é
          registrado — vive no PRIVACY_NOTICE, em Configurações → Privacidade.
          Esta linha existe para que a escolha continue informada: sem um
          caminho nomeado para o texto completo, o consentimento deixa de ser
          específico, que é a base legal inteira. É o mínimo, não decoração. */}
      <p style={{ fontSize: 11.5, lineHeight: 1.6, color: theme.subtext, margin: '0 0 14px' }}>
        Você muda de ideia quando quiser em Configurações&nbsp;→&nbsp;Privacidade.
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={button} onClick={decide(revokeConsent)}>Agora não</button>
        <button style={button} onClick={decide(grantConsent)}>Pode guardar</button>
      </div>
    </div>
  );
}
