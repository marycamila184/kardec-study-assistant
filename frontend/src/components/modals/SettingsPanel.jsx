import React, { useState } from 'react';

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
export default function SettingsPanel({
  open, onClose, darkMode, onToggleDark,
  fontSize, onFontSize,
  reminderOn, onToggleReminder, reminderTime, onReminderTime,
  notifPermission, onRequestNotif,
  theme,
}) {
  if (!open) return null;

  const [justSaved, setJustSaved] = useState(false);

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
          <button onClick={onClose} style={{
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
