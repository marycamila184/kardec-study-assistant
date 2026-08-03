import React from 'react';

const LEVEL_LABEL = { curioso: 'Iniciante', estudante: 'Intermediário', aprofundado: 'Avançado' };
const LEVEL_ORDER = ['curioso', 'estudante', 'aprofundado'];

const PRIMARY_BTN = {
  background: '#6B9BB8', color: 'white', border: 'none',
  padding: '8px 16px', borderRadius: 7, fontSize: 12, fontWeight: 600,
  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
};
const SECONDARY_BTN = {
  background: 'transparent', color: '#4A7A98',
  border: '1px solid rgba(107,155,184,.35)',
  padding: '8px 16px', borderRadius: 7, fontSize: 12, fontWeight: 600,
  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
};

// A badge is a pill: it either fits on a line or moves to the next one, but it
// never breaks in half. Without nowrap + flexShrink:0 the flex row squeezes the
// span instead of wrapping the row, and "Em andamento" — the longest label —
// splits across two lines inside its own background. That shows up on mobile
// only in the in-progress state, which is also the state that adds a second
// button to the right column, so the badges get the least room exactly when
// they need the most.
const BADGE = {
  fontSize: 10.5, fontWeight: 700, letterSpacing: '.1em',
  padding: '2px 8px', borderRadius: 3, textTransform: 'uppercase',
  whiteSpace: 'nowrap', flexShrink: 0,
};

export default function EstudarPicker({ theme, onStartTrilha, onResumeTrilha, onExplorar, onVerIntro, paths = [], pathsLoading = false, completedTrilhas = [], trilhaProgress = {}, isMobile = false }) {
  // Text beside buttons is the desktop shape. On a phone the button column is
  // flexShrink:0, so every pixel it takes comes out of the text column — which
  // is what squeezed the badges. Stacking gives the text the full width and
  // lets the actions share a row of their own.
  const CARD_ROW = {
    display: 'flex',
    flexDirection: isMobile ? 'column' : 'row',
    alignItems: isMobile ? 'stretch' : 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  };
  const ACTIONS = {
    display: 'flex',
    flexDirection: isMobile ? 'row' : 'column',
    gap: 6,
    flexShrink: 0,
  };
  // flex:1 overrides the shared buttons' flexShrink:0, so a stacked pair splits
  // the width evenly instead of leaving a ragged gap.
  const btn = (base) => (isMobile ? { ...base, flex: 1 } : base);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>
      {/* No title here: the TopBar already names the mode. This line is the
          screen's instruction, which is different content. */}
      <div style={{ marginBottom: 22 }}>
        {/* theme.text, not subtext: this is now the screen's leading line,
            not a caption. subtext is 2.92:1 on the light background —
            below the 4.5:1 floor, and unreadable as primary copy. */}
        <div style={{ fontSize: 15.5, color: theme.text, lineHeight: 1.6, maxWidth: 620 }}>
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
          <div style={CARD_ROW}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 7, rowGap: 5, marginBottom: 5 }}>
                <span style={{ ...BADGE, background: 'rgba(107,155,184,.12)', color: '#4A7A98' }}>Contexto</span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 4 }}>
                Sobre Allan Kardec e as obras
              </div>
              <div style={{ fontSize: 13.5, color: theme.subtext, lineHeight: 1.55 }}>
                Conheça o autor e o Pentateuco Espírita antes de começar seus estudos.
              </div>
            </div>
            <div style={ACTIONS}>
              <button onClick={onVerIntro} style={btn(PRIMARY_BTN)}>Ver →</button>
            </div>
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
              {group.map(tr => {
                const completed = completedTrilhas.includes(tr.id);
                const total = tr.step_count || 0;
                const rawStep = trilhaProgress[tr.id]?.step || 0;
                const step = Math.min(rawStep, total);
                const inProgress = !completed && step > 0;
                const pct = total > 0 ? Math.round((step / total) * 100) : 0;
                return (
                <div key={tr.id} style={{
                  background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                  borderRadius: 10, padding: '16px 18px', marginBottom: 8,
                }}>
                  <div style={CARD_ROW}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 7, rowGap: 5, marginBottom: 5 }}>
                        <span style={{ ...BADGE, background: 'rgba(107,155,184,.12)', color: '#4A7A98' }}>
                          {LEVEL_LABEL[level]}
                        </span>
                        <span style={{ fontSize: 10, color: theme.subtext, whiteSpace: 'nowrap', flexShrink: 0 }}>
                          {tr.step_count} trechos
                        </span>
                        {completed && (
                          <span style={{ ...BADGE, background: 'rgba(90,170,100,.12)', color: '#4A9A5A' }}>
                            ✓ Concluída
                          </span>
                        )}
                        {inProgress && (
                          <span style={{ ...BADGE, background: 'rgba(200,133,106,.12)', color: '#B5714E' }}>
                            Em andamento
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 4 }}>{tr.title}</div>
                      <div style={{ fontSize: 13.5, color: theme.subtext, lineHeight: 1.55 }}>{tr.description}</div>
                      {inProgress && (
                        <div style={{ marginTop: 10 }}>
                          <div style={{ fontSize: 11, color: theme.subtext, marginBottom: 4 }}>
                            Passo {step} de {total}
                          </div>
                          <div style={{ height: 4, borderRadius: 2, background: theme.cardBorder, overflow: 'hidden' }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: '#6B9BB8' }} />
                          </div>
                        </div>
                      )}
                    </div>
                    <div style={ACTIONS}>
                      {inProgress ? (
                        <>
                          <button onClick={() => onResumeTrilha(tr)} style={btn(PRIMARY_BTN)}>Continuar →</button>
                          <button onClick={() => onStartTrilha(tr)} style={btn(SECONDARY_BTN)}>Recomeçar</button>
                        </>
                      ) : completed ? (
                        <button onClick={() => onStartTrilha(tr)} style={btn(SECONDARY_BTN)}>Refazer</button>
                      ) : (
                        <button onClick={() => onStartTrilha(tr)} style={btn(PRIMARY_BTN)}>Iniciar →</button>
                      )}
                    </div>
                  </div>
                </div>
                );
              })}
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
          ...CARD_ROW,
          alignItems: isMobile ? 'stretch' : 'center',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, marginBottom: 3 }}>Explorar Obras</div>
            <div style={{ fontSize: 13.5, color: theme.subtext }}>Navegue pelos tópicos de cada obra e consulte temas específicos.</div>
          </div>
          <div style={ACTIONS}>
            <button onClick={onExplorar} style={btn(SECONDARY_BTN)}>Explorar →</button>
          </div>
        </div>
      </div>
    </div>
  );
}
