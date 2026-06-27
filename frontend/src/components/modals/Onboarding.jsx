import React, { useState } from 'react';
import { OBRAS } from '../../constants/obras';

/**
 * 3-step onboarding overlay.
 * Props:
 *   onFinish(selectedObraId) — called when user completes onboarding
 */
export default function Onboarding({ onFinish }) {
  const [step, setStep] = useState(0);
  const [selectedObra, setSelectedObra] = useState('le');

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
            Um companheiro de estudos da doutrina espírita, fundamentado nas obras de Allan Kardec.
            Respostas transparentes, acessíveis e sempre com referências.
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
              Esta IA foi refinada para trabalhar <strong>exclusivamente com o Pentateuco Espírita</strong> —
              as cinco obras de Allan Kardec. Toda resposta é fundamentada e referenciada nessas fontes.
            </div>
          </div>
          <button onClick={() => setStep(1)} style={{
            background: '#6B9BB8', color: 'white', border: 'none',
            padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}>Começar →</button>
          <Dots total={3} active={0} />
        </div>
      )}

      {step === 1 && (
        <div style={{ maxWidth: 580, width: '100%', animation: 'fade-up .5s ease' }}>
          <div style={{ textAlign: 'center', marginBottom: 26 }}>
            <div style={{
              fontFamily: "'Crimson Pro', serif", fontSize: 28, fontWeight: 600,
              color: '#2A2318', marginBottom: 7,
            }}>Quatro formas de estudar</div>
            <div style={{ fontSize: 13, color: '#9A8878' }}>
              Mude de modo a qualquer momento conforme sua necessidade
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 28 }}>
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
          <div style={{ textAlign: 'center' }}>
            <button onClick={() => setStep(2)} style={{
              background: '#6B9BB8', color: 'white', border: 'none',
              padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}>Entendi →</button>
            <Dots total={3} active={1} />
          </div>
        </div>
      )}

      {step === 2 && (
        <div style={{ textAlign: 'center', maxWidth: 500, animation: 'fade-up .5s ease' }}>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 28, fontWeight: 600,
            color: '#2A2318', marginBottom: 8,
          }}>Por onde começar?</div>
          <div style={{ fontSize: 13, color: '#9A8878', marginBottom: 28 }}>
            Escolha a obra em foco — você pode mudar a qualquer momento
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9, justifyContent: 'center', marginBottom: 32 }}>
            {OBRAS.map(o => (
              <button key={o.id} onClick={() => setSelectedObra(o.id)} style={{
                background: selectedObra === o.id ? '#6B9BB8' : 'white',
                color: selectedObra === o.id ? 'white' : '#4A6070',
                border: `1px solid ${selectedObra === o.id ? '#6B9BB8' : '#D8D0C4'}`,
                fontSize: 12, padding: '7px 15px', borderRadius: 20, cursor: 'pointer',
              }}>{o.label}</button>
            ))}
          </div>
          <button onClick={() => onFinish(selectedObra)} style={{
            background: '#6B9BB8', color: 'white', border: 'none',
            padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}>Começar a estudar →</button>
          <Dots total={3} active={2} />
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
  { title: 'Estudar uma Obra', desc: 'Consulte questões, capítulos e temas específicos das obras de Kardec.', icon: '📚' },
  { title: 'Tirar uma Dúvida', desc: 'Perguntas abertas com respostas fundamentadas e referências claras.', icon: '💬' },
  { title: 'Refletir',           desc: 'Relacione situações da sua vida aos ensinamentos da doutrina espírita.', icon: '⭐' },
  { title: 'Estudo Diário',      desc: 'Trecho do dia, reflexão e pergunta para meditação. 3 a 5 minutos.', icon: '☀️' },
];
