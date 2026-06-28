import React from 'react';

const LEVEL_LABEL = { curioso: 'Iniciante', estudante: 'Intermediário', aprofundado: 'Avançado' };
const LEVEL_ORDER = ['curioso', 'estudante', 'aprofundado'];

export default function EstudarPicker({ theme, onStartTrilha, onExplorar, onVerIntro, paths = [], pathsLoading = false, completedTrilhas = [] }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 22, fontWeight: 600, color: theme.text, marginBottom: 6 }}>
          Estudar uma Obra
        </div>
        <div style={{ fontSize: 14, color: theme.subtext, lineHeight: 1.65 }}>
          Escolha entre o estudo guiado — com tutor socrático — ou a exploração livre.
        </div>
      </div>

      {/* Sobre as Obras — mesmo padrão das trilhas */}
      <div style={{ marginBottom: 24 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Introdução</div>
        <div style={{
          background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
          borderRadius: 10, padding: '16px 18px',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                <span style={{
                  background: 'rgba(107,155,184,.12)', color: '#4A7A98',
                  fontSize: 10.5, fontWeight: 700, letterSpacing: '.1em',
                  padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
                }}>Contexto</span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 4 }}>
                Sobre Allan Kardec e as obras
              </div>
              <div style={{ fontSize: 13.5, color: theme.subtext, lineHeight: 1.55 }}>
                Conheça o autor e o Pentateuco Espírita antes de começar seus estudos.
              </div>
            </div>
            <button onClick={onVerIntro} style={{
              background: '#6B9BB8', color: 'white', border: 'none',
              padding: '8px 16px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            }}>Ver →</button>
          </div>
        </div>
      </div>

      {/* Trilhas guiadas — agrupadas por nível */}
      <div style={{ borderTop: `1px solid ${theme.cardBorder}`, paddingTop: 14, marginBottom: 14 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Trilhas guiadas</div>
        {pathsLoading && (
          <div style={{ color: theme.subtext, fontSize: 12, padding: '10px 0' }}>Carregando trilhas…</div>
        )}
        {!pathsLoading && paths.length === 0 && (
          <div style={{ color: theme.subtext, fontSize: 12, padding: '10px 0' }}>Nenhuma trilha disponível no momento.</div>
        )}
        {!pathsLoading && LEVEL_ORDER.map(level => {
          const group = paths.filter(tr => tr.level === level);
          if (group.length === 0) return null;
          return (
            <div key={level} style={{ marginBottom: 16 }}>
              {group.map(tr => (
                <div key={tr.id} style={{
                  background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                  borderRadius: 10, padding: '16px 18px', marginBottom: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                        <span style={{
                          background: 'rgba(107,155,184,.12)', color: '#4A7A98',
                          fontSize: 10.5, fontWeight: 700, letterSpacing: '.1em',
                          padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
                        }}>{LEVEL_LABEL[level]}</span>
                        <span style={{ fontSize: 10, color: theme.subtext }}>{tr.step_count} trechos</span>
                        {completedTrilhas.includes(tr.id) && (
                          <span style={{
                            background: 'rgba(90,170,100,.12)', color: '#4A9A5A',
                            fontSize: 10.5, fontWeight: 700, letterSpacing: '.1em',
                            padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
                          }}>✓ Concluída</span>
                        )}
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 4 }}>{tr.title}</div>
                      <div style={{ fontSize: 13.5, color: theme.subtext, lineHeight: 1.55 }}>{tr.description}</div>
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
          );
        })}
      </div>

      {/* Consulta livre */}
      <div style={{ borderTop: `1px solid ${theme.cardBorder}`, paddingTop: 14 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 10,
        }}>Consulta livre</div>
        <div style={{
          background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
          borderRadius: 10, padding: '16px 18px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 3 }}>Explorar Obras</div>
            <div style={{ fontSize: 13.5, color: theme.subtext }}>Navegue pelos tópicos de cada obra e consulte temas específicos.</div>
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
