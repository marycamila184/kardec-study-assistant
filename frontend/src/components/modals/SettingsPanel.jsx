import { ANALYTICS_NOTICE, CONTACT_FORM_URL, LOCAL_STORAGE_NOTICE, PRIVACY_NOTICE } from '../../constants/contact';
import React, { useState } from 'react';
import { useEscapeKey } from '../../hooks/useEscapeKey';

/**
 * Slide-in settings panel from the right (300px wide).
 * Props:
 *   open           — boolean
 *   onClose        — () => void
 *   darkMode       — boolean
 *   onToggleDark   — () => void
 *   fontSize       — 'small' | 'medium' | 'large'
 *   onFontSize     — (size) => void
 *   reminderOn     — boolean
 *   onToggleReminder — () => void
 *   reminderTime   — string 'HH:MM'
 *   onReminderTime — (time) => void
 *   notifPermission — 'default' | 'granted' | 'denied'
 *   onRequestNotif — () => void
 *   theme
 */
const CITATION_LABELS = {
  inline: 'no texto',
  chips: 'ao lado da resposta',
  none: 'sem citações',
};

const DEPTH_LABELS = {
  breve: 'respostas curtas',
  normal: 'normal',
  aprofundado: 'mais desenvolvidas',
};

const VOCABULARY_LABELS = {
  iniciante: 'explicando os termos',
  corrente: 'normal',
  tecnico: 'termos da doutrina sem explicar',
};

export default function SettingsPanel({
  open, onClose, darkMode, onToggleDark,
  fontSize, onFontSize,
  reminderOn, onToggleReminder, reminderTime, onReminderTime,
  notifPermission, onRequestNotif,
  profile, onResetProfile,
  theme,
}) {
  const [justSaved, setJustSaved] = useState(false);
  useEscapeKey(onClose, open);

  if (!open) return null;

  const Toggle = ({ on, onToggle }) => (
    <div onClick={onToggle} style={{
      width: 40, height: 22, borderRadius: 11,
      background: on ? '#6B9BB8' : '#CCC',
      position: 'relative', cursor: 'pointer', transition: 'background .2s', flexShrink: 0,
    }}>
      <div style={{
        width: 16, height: 16, borderRadius: '50%', background: 'white',
        position: 'absolute', top: 3, left: on ? 21 : 3,
        transition: 'left .2s', boxShadow: '0 1px 4px rgba(0,0,0,.25)',
      }} />
    </div>
  );

  const fontBtns = ['small', 'medium', 'large'];
  const fontLabels = { small: 'Pequena', medium: 'Média', large: 'Grande' };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 80, display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,.28)' }} onClick={onClose} />
      <div style={{
        width: 300, background: theme.headerBg,
        display: 'flex', flexDirection: 'column', zIndex: 1,
        boxShadow: '-4px 0 32px rgba(0,0,0,.16)',
        animation: 'slide-in-right .24s ease',
      }}>
        <div style={{
          padding: '18px 20px', borderBottom: `1px solid ${theme.headerBorder}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
        }}>
          <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 17, fontWeight: 600, color: theme.text }}>
            Configurações
          </div>
          <button onClick={onClose} aria-label="Fechar configurações" style={{
            width: 28, height: 28, borderRadius: 6,
            background: 'transparent', border: `1px solid ${theme.headerBorder}`,
            cursor: 'pointer', fontSize: 18, color: theme.subtext,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 22 }}>

          {/* Aparência */}
          <Section title="Aparência" theme={theme}>
            <Row label="Modo escuro" sublabel="" theme={theme}>
              <Toggle on={darkMode} onToggle={onToggleDark} />
            </Row>
            <div style={{ fontSize: 12, color: theme.subtext, marginBottom: 8, fontWeight: 500 }}>Tamanho da fonte</div>
            <div style={{ display: 'flex', gap: 6 }}>
              {fontBtns.map(s => (
                <button key={s} onClick={() => onFontSize(s)} style={{
                  flex: 1, fontSize: 11.5, padding: '6px 4px', borderRadius: 6, cursor: 'pointer',
                  border: `1px solid ${fontSize === s ? '#6B9BB8' : theme.headerBorder}`,
                  background: fontSize === s ? '#6B9BB8' : 'transparent',
                  color: fontSize === s ? 'white' : theme.text,
                  fontWeight: fontSize === s ? 600 : 400,
                }}>{fontLabels[s]}</button>
              ))}
            </div>
          </Section>

          {/* Sobre a IA */}
          <Section title="Sobre esta IA" theme={theme}>
            <div style={{ background: 'rgba(107,155,184,.07)', border: '1px solid rgba(107,155,184,.2)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: theme.text, marginBottom: 8 }}>Escopo e fontes</div>
              <p style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.7, margin: '0 0 10px' }}>
                Esta IA foi refinada para trabalhar <strong style={{ color: theme.text }}>exclusivamente com o Pentateuco Espírita</strong>.
              </p>
              <div style={{ padding: '8px 10px', background: 'rgba(200,133,106,.08)', border: '1px solid rgba(200,133,106,.2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: theme.subtext, lineHeight: 1.6 }}>
                  ⚠️ Perguntas fora do escopo das obras de Kardec serão redirecionadas ou não respondidas.
                </div>
              </div>
            </div>
          </Section>

          {/* How the answers are currently shaped.
              Here, and deliberately nowhere else. The conversation never
              announces a change — the reader asked in their own words and the
              answer simply arrives already shaped, with no banner and no "modo
              alterado". But silent AND unfindable is the one combination to
              avoid: that is how someone ends up unable to undo something they
              never saw happen. So it lives where a person goes when they wonder
              why, not in the flow where it would interrupt.
              See docs/superpowers/specs/2026-07-28-adaptive-response-profile-design.md */}
          {profile && (
            <Section title="Como as respostas estão saindo" theme={theme}>
              <div style={{ fontSize: 13, color: theme.text, lineHeight: 1.8 }}>
                <div>Citações: {CITATION_LABELS[profile.citation_style] || profile.citation_style}</div>
                <div>Referência: {profile.citation_precision === 'full' ? 'completa (obra, capítulo e item)' : 'curta'}</div>
                <div>Profundidade: {DEPTH_LABELS[profile.depth] || profile.depth}</div>
                <div>Linguagem: {VOCABULARY_LABELS[profile.vocabulary] || profile.vocabulary}</div>
              </div>
              <div style={{ fontSize: 11.5, color: theme.subtext, marginTop: 10, lineHeight: 1.6 }}>
                Isso se ajusta sozinho conforme a conversa, e muda na hora se você
                pedir — "traga as citações", "explique mais simples".
              </div>
              <button onClick={onResetProfile} style={{
                marginTop: 12, background: 'transparent',
                border: `1px solid ${theme.cardBorder}`, color: theme.subtext,
                fontSize: 12, padding: '6px 12px', borderRadius: 7, cursor: 'pointer',
              }}>Voltar ao padrão</button>
            </Section>
          )}

          {/* Privacy — moved out of onboarding, where it competed with the
              introduction to the project and was read at the worst moment:
              before the reader had any reason to care. Here it is found by
              whoever goes looking for it. */}
          <Section title="Privacidade" theme={theme}>
            <div style={{ background: 'rgba(107,155,184,.07)', border: '1px solid rgba(107,155,184,.2)', borderRadius: 8, padding: 14 }}>
              <p style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.7, margin: '0 0 10px' }}>
                {LOCAL_STORAGE_NOTICE}
              </p>
              <p style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.7, margin: '0 0 10px' }}>
                {PRIVACY_NOTICE}
              </p>
              <p style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.7, margin: 0 }}>
                {ANALYTICS_NOTICE}
              </p>
              {CONTACT_FORM_URL && (
                <a href={CONTACT_FORM_URL} target="_blank" rel="noopener noreferrer" style={{
                  display: 'inline-block', marginTop: 10, fontSize: 12,
                  color: '#6B9BB8', textDecoration: 'none', fontWeight: 500,
                }}>Fale comigo →</a>
              )}
            </div>
          </Section>

          {/* Idioma */}
          <Section title="Idioma" theme={theme}>
            <div style={{ display: 'flex', gap: 6 }}>
              <button style={{
                background: '#6B9BB8', color: 'white', border: '1px solid #6B9BB8',
                fontSize: 12, padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
              }}>Português (PT-BR)</button>
              <button style={{
                background: 'transparent', color: theme.subtext,
                border: `1px solid ${theme.headerBorder}`,
                fontSize: 12, padding: '6px 14px', borderRadius: 6, cursor: 'not-allowed', opacity: 0.5,
              }}>English (em breve)</button>
            </div>
          </Section>

          {/* Lembrete */}
          <Section title="Lembrete de Estudo" theme={theme}>
            <Row label="Ativar lembrete diário" sublabel="Notificação no horário escolhido" theme={theme}>
              <Toggle on={reminderOn} onToggle={onToggleReminder} />
            </Row>
            {reminderOn && (
              <>
                <input type="time" value={reminderTime} onChange={e => {
                  onReminderTime(e.target.value);
                  setJustSaved(true);
                  setTimeout(() => setJustSaved(false), 1500);
                }} style={{
                  width: '100%', background: theme.inputBg,
                  border: `1px solid ${theme.headerBorder}`,
                  borderRadius: 7, padding: '8px 10px', fontSize: 13, color: theme.text,
                  marginBottom: 4,
                }} />
                <div style={{ fontSize: 11, color: '#6B9BB8', minHeight: 14, marginBottom: 6 }}>
                  {justSaved ? 'Salvo ✓' : ''}
                </div>
                <button onClick={onRequestNotif} style={{
                  width: '100%', padding: 8, borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                  border: `1px solid ${notifPermission === 'granted' ? '#6B9BB8' : theme.headerBorder}`,
                  background: notifPermission === 'granted' ? 'rgba(107,155,184,.1)' : 'transparent',
                  color: notifPermission === 'granted' ? '#6B9BB8' : theme.text,
                }}>
                  {notifPermission === 'granted' ? '✓ Notificações ativas' : 'Ativar notificações do navegador'}
                </button>
              </>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children, theme }) {
  return (
    <div>
      <div style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
        textTransform: 'uppercase', color: theme.subtext, marginBottom: 12,
      }}>{title}</div>
      {children}
    </div>
  );
}

function Row({ label, sublabel, children, theme }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <div>
        <div style={{ fontSize: 13, color: theme.text, fontWeight: 500 }}>{label}</div>
        {sublabel && <div style={{ fontSize: 11, color: theme.subtext, marginTop: 2 }}>{sublabel}</div>}
      </div>
      {children}
    </div>
  );
}
