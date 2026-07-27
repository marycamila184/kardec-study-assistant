import React from 'react';

/**
 * First-run overlay: a single welcome screen.
 *
 * It exists for the one thing HomeLauncher never says — that the assistant
 * works exclusively with the Pentateuco Espírita and is not meant to replace
 * reading the works. That framing is what keeps a reader from reading a
 * `not_found` as a bug.
 *
 * It deliberately does NOT preview the three modes. HomeLauncher renders them
 * one click later, from `constants/modes.js`; a second copy here would be a
 * second source of truth for the mode labels, which is exactly how this file
 * came to be teaching names ("Estudar uma Obra", "Tirar uma Dúvida") the app
 * had already stopped using.
 *
 * Props:
 *   onFinish() — called when the reader dismisses the overlay
 */
import { CONTACT_FORM_URL, LOCAL_STORAGE_NOTICE, PRIVACY_NOTICE } from '../../constants/contact';

export default function Onboarding({ onFinish }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, background: '#EEE9E2',
    }}>
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
          Estude · Dialogue · Compreenda
        </div>
        <p style={{ fontSize: 14, color: '#6A5E50', lineHeight: 1.78, margin: '0 0 16px' }}>
          Aqui você estuda e tira dúvidas sobre as obras de Allan Kardec, e encontra
          todo dia um novo trecho do Evangelho — com respostas sempre fundamentadas
          e referenciadas nos próprios textos.
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
        <p style={{ fontSize: 11.5, color: '#8A7E70', lineHeight: 1.6, margin: '0 0 22px' }}>
          {LOCAL_STORAGE_NOTICE} {PRIVACY_NOTICE}
          {CONTACT_FORM_URL && (
            <> <a href={CONTACT_FORM_URL} target="_blank" rel="noopener noreferrer"
              style={{ color: '#6B9BB8' }}>Fale comigo</a>.</>
          )}
        </p>
        <button onClick={onFinish} style={{
          background: '#6B9BB8', color: 'white', border: 'none',
          padding: '13px 36px', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>Começar →</button>
      </div>
    </div>
  );
}
