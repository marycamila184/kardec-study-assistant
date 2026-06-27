import React from 'react';
import { OBRAS } from '../../constants/obras';

const LEVEL_LABEL = { curioso: 'Iniciante', estudante: 'Intermediário', aprofundado: 'Avançado' };

/**
 * The "Estudar uma Obra" picker screen.
 * Shows: Quem foi Kardec + Pentateuco + Trilhas guiadas + Explorar Obras card
 */
export default function EstudarPicker({ theme, onStartTrilha, onExplorar, paths = [], pathsLoading = false }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 22, fontWeight: 600, color: theme.text, marginBottom: 6 }}>
          Estudar uma Obra
        </div>
        <div style={{ fontSize: 12.5, color: theme.subtext, lineHeight: 1.65 }}>
          Escolha entre o estudo guiado — com tutor socrático — ou a exploração livre.
        </div>
      </div>

      {/* Quem foi Kardec */}
      <div style={{
        background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
        borderRadius: 10, padding: '16px 18px', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div style={{
            width: 38, height: 38, borderRadius: '50%',
            background: 'rgba(107,155,184,.12)', border: '1px solid rgba(107,155,184,.22)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <svg width={17} height={17} viewBox="0 0 24 24" fill="none"
              stroke="#6B9BB8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div>
            <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 16, fontWeight: 600, color: theme.text }}>
              Quem foi Allan Kardec?
            </div>
            <div style={{ fontSize: 10, color: theme.subtext }}>Lyon, 1804 — Paris, 1869</div>
          </div>
        </div>
        <p style={{ fontSize: 12.5, color: theme.text, lineHeight: 1.75, margin: '0 0 10px' }}>
          Hippolyte Léon Denizard Rivail foi um pedagogo e escritor francês que, sob o pseudônimo{' '}
          <strong>Allan Kardec</strong>, codificou o Espiritismo. Entre 1857 e 1868, publicou as cinco obras
          que formam o <strong>Pentateuco Espírita</strong>.
        </p>
        <div style={{
          padding: '10px 12px', background: 'rgba(107,155,184,.07)',
          borderLeft: '3px solid #6B9BB8', borderRadius: '0 6px 6px 0',
        }}>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 13.5, fontStyle: 'italic',
            color: theme.obraText, lineHeight: 1.65,
          }}>"O Espiritismo não é uma religião, nem uma seita: é uma ciência."</div>
          <div style={{ fontSize: 10, color: theme.subtext, marginTop: 5 }}>— Allan Kardec, A Gênese, cap. I</div>
        </div>
      </div>

      {/* O Pentateuco */}
      <div style={{ marginBottom: 20 }}>
        <div style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 12,
        }}>O Pentateuco Espírita</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {OBRAS.map(o => (
            <div key={o.id} style={{
              background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
              borderRadius: 8, padding: '12px 14px', display: 'flex', alignItems: 'flex-start', gap: 12,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 6,
                background: 'rgba(107,155,184,.1)', border: '1px solid rgba(107,155,184,.18)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, fontFamily: "'Crimson Pro', serif", fontSize: 13, fontWeight: 600, color: '#6B9BB8',
              }}>{o.abbr}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: theme.text, marginBottom: 3 }}>{o.label}</div>
                <div style={{ fontSize: 10.5, color: theme.subtext, lineHeight: 1.55 }}>{o.summary}</div>
                <div style={{ fontSize: 9.5, color: 'rgba(107,155,184,.7)', marginTop: 4, fontStyle: 'italic' }}>{o.year}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Trilhas guiadas */}
      <div style={{ marginBottom: 14 }}>
        <div style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Trilhas guiadas</div>
        {pathsLoading && (
          <div style={{ color: theme.subtext, fontSize: 12, padding: '10px 0' }}>
            Carregando trilhas…
          </div>
        )}
        {!pathsLoading && paths.length === 0 && (
          <div style={{ color: theme.subtext, fontSize: 12, padding: '10px 0' }}>
            Nenhuma trilha disponível no momento.
          </div>
        )}
        {!pathsLoading && paths.map(tr => (
          <div key={tr.id} style={{
            background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
            borderRadius: 10, padding: '16px 18px', marginBottom: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                  <span style={{
                    background: 'rgba(107,155,184,.12)', color: '#4A7A98',
                    fontSize: 9, fontWeight: 700, letterSpacing: '.1em',
                    padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
                  }}>{LEVEL_LABEL[tr.level] || tr.level}</span>
                  <span style={{ fontSize: 10, color: theme.subtext }}>{tr.step_count} trechos</span>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: theme.text, marginBottom: 4 }}>{tr.title}</div>
                <div style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.55 }}>{tr.description}</div>
              </div>
              <button onClick={() => onStartTrilha(tr)} style={{
                background: '#6B9BB8', color: 'white', border: 'none',
                padding: '8px 16px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}>Iniciar →</button>
            </div>
          </div>
        ))}
      </div>

      {/* Explorar Obras */}
      <div style={{ borderTop: `1px solid ${theme.cardBorder}`, paddingTop: 14 }}>
        <div style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Consulta livre</div>
        <div style={{
          background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
          borderRadius: 10, padding: '16px 18px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: theme.text, marginBottom: 3 }}>Explorar Obras</div>
            <div style={{ fontSize: 12, color: theme.subtext }}>Navegue pelos tópicos de cada obra e consulte temas específicos.</div>
          </div>
          <button onClick={onExplorar} style={{
            background: 'transparent', color: '#4A7A98',
            border: '1px solid rgba(107,155,184,.35)',
            padding: '8px 16px', borderRadius: 7, fontSize: 12, fontWeight: 600,
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          }}>Explorar →</button>
        </div>
      </div>
    </div>
  );
}
