import React, { useState } from 'react';

/**
 * 2-step onboarding overlay.
 * Props:
 *   onFinish() — called when user completes onboarding
 */
export default function Onboarding({ onFinish }) {
  const [step, setStep] = useState(0);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: '#EEE9E2',
    }}>
      {step === 0 && (
        <div style={{ textAlign: 'center', maxWidth: 440, animation: 'fade-up .5s ease' }}>
          <div style={{
            width: 68, height: 68, borderRadius: '50%', background: '#6B9BB8',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 24px', boxShadow: '0 4px 20px rgba(107,155,184,.4)',
          }}>
            <svg width={28} height={28} viewBox="0 0 24 24" fill="none"
              stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
          </div>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 38, fontWeight: 600,
            color: '#2A2318', lineHeight: 1.18, marginBottom: 10, letterSpacing: '-.01em',
          }}>Dialogando com<br/>a Doutrina</div>
          <div style={{ fontSize: 10, letterSpacing: '.22em', textTransform: 'uppercase', color: '#A09080', marginBottom: 22 }}>
            Estude · Reflita · Compreenda
          </div>
          <p style={{ fontSize: 14, color: '#6A5E50', lineHeight: 1.78, margin: '0 0 16px' }}>
            Aqui você estuda, tira dúvidas e reflete sobre as obras de Allan Kardec —
            com respostas sempre fundamentadas e referenciadas nos próprios textos.
          </p>
          <div style={{
            background: 'rgba(107,155,184,.1)', border: '1px solid rgba(107,155,184,.25)',
            borderRadius: 8, padding: '12px 16px', marginBottom: 28,
            display: 'flex', gap: 10, alignItems: 'flex-start',
          }}>
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none"
              stroke="#6B9BB8" strokeWidth="1.8" strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div style={{ fontSize: 12.5, color: '#5A6E7A', lineHeight: 1.65 }}>
              Funciona exclusivamente com o <strong>Pentateuco Espírita</strong> —
              as cinco obras de Kardec. O objetivo não é substituir a leitura, mas torná-la mais acessível.
            </div>
          </div>
          <button onClick={() => setStep(1)} style={{
            background: '#6B9BB8', color: 'white', border: 'none',
            padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}>Começar →</button>
          <Dots total={2} active={0} />
        </div>
      )}

      {step === 1 && (
        <div style={{ maxWidth: 580, width: '100%', animation: 'fade-up .5s ease' }}>
          <div style={{ textAlign: 'center', marginBottom: 26 }}>
            <div style={{
              fontFamily: "'Crimson Pro', serif", fontSize: 28, fontWeight: 600,
              color: '#2A2318', marginBottom: 7,
            }}>Como você quer estudar hoje?</div>
            <div style={{ fontSize: 13, color: '#9A8878' }}>
              Escolha o modo que combina com o seu momento — você pode mudar a qualquer hora
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
            {STEP1_MODES.map(m => (
              <div key={m.title} style={{
                background: 'white', border: '1px solid #E8E2D8', borderRadius: 10, padding: 16,
              }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 8, background: 'rgba(107,155,184,.1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 11,
                }}>{m.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#2A2318', marginBottom: 4 }}>{m.title}</div>
                <div style={{ fontSize: 12, color: '#9A8878', lineHeight: 1.6 }}>{m.desc}</div>
              </div>
            ))}
          </div>
          <div style={{
            background: 'rgba(200,133,106,.07)', border: '1px solid rgba(200,133,106,.25)',
            borderRadius: 10, padding: '12px 16px', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 34, height: 34, borderRadius: 8, background: 'rgba(200,133,106,.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>{STEP1_FEATURE.icon}</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#2A2318', marginBottom: 2 }}>{STEP1_FEATURE.title}</div>
              <div style={{ fontSize: 12, color: '#9A8878', lineHeight: 1.6 }}>{STEP1_FEATURE.desc}</div>
            </div>
            <div style={{
              marginLeft: 'auto', fontSize: 10, fontWeight: 700, letterSpacing: '.1em',
              textTransform: 'uppercase', color: '#C8856A', flexShrink: 0,
            }}>Sidebar</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <button onClick={() => setStep(0)} style={{
              background: 'transparent', color: '#9A8878',
              border: '1px solid #D8D0C4',
              padding: '13px 24px', borderRadius: 8, fontSize: 14, fontWeight: 500, cursor: 'pointer',
            }}>← Voltar</button>
            <button onClick={() => onFinish()} style={{
              background: '#6B9BB8', color: 'white', border: 'none',
              padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}>Começar a estudar →</button>
          </div>
          <Dots total={2} active={1} />
        </div>
      )}
    </div>
  );
}

function Dots({ total, active }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginTop: 20 }}>
      {Array.from({ length: total }).map((_, i) => (
        <span key={i} style={{
          width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
          background: i === active ? '#6B9BB8' : '#D8D0C4',
        }} />
      ))}
    </div>
  );
}

const STEP1_MODES = [
  { title: 'Estudar uma Obra', desc: 'Siga uma trilha guiada com tutor, ou explore livremente questões e capítulos de cada obra.', icon: '📚' },
  { title: 'Tirar uma Dúvida', desc: 'Faça qualquer pergunta sobre a doutrina e receba uma resposta com a referência exata de onde ela veio.', icon: '💬' },
  { title: 'Refletir',         desc: 'Traga uma situação da sua vida e encontre conexões com os ensinamentos espíritas — sem julgamentos, só reflexão.', icon: '⭐' },
];

const STEP1_FEATURE = {
  title: 'Trecho do dia',
  desc: 'Um trecho do Evangelho por dia, sempre disponível na barra lateral.',
  icon: '☀️',
};
