import React from 'react';

const LEVEL_LABEL = { curioso: 'Iniciante', estudante: 'Intermediário', aprofundado: 'Avançado' };

const BookIcon = ({ size = 17, color = 'white' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);

const navModes = [
  { id: 'estudar',  label: 'Estudar uma Obra' },
  { id: 'duvida',   label: 'Tirar uma Dúvida' },
  { id: 'refletir', label: 'Refletir' },
];

/**
 * Desktop sidebar (300px wide, sky blue background).
 * Props:
 *   mode           — current active mode string
 *   onModeChange   — (modeId: string) => void
 *   onStudyTrecho  — () => void  (opens daily trecho in chat)
 *   onTutorial     — () => void
 *   conversations  — array of {id, title, mode, msgs}
 *   onLoadConvo    — (convo) => void
 *   favorites      — array of {id, ia, obra}
 */
export default function Sidebar({
  mode, onModeChange,
  onStudyTrecho, onTutorial,
  conversations = [], onLoadConvo, onDeleteConvo, onToggleConvoFavorite,
  favorites = [],
  evangelhoData = null,
  onClose,
}) {
  const navBase = {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '7px 8px', borderRadius: 6, cursor: 'pointer',
    fontSize: 13, marginBottom: 2, transition: 'background .15s',
  };

  return (
    <div style={{
      width: 300, background: '#6B9BB8',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
    }}>
      {/* Brand */}
      <div
        onClick={onTutorial}
        style={{ padding: '18px 14px 8px', cursor: onTutorial ? 'pointer' : 'default' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 9,
            background: 'rgba(255,255,255,.18)', border: '1px solid rgba(255,255,255,.26)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <BookIcon />
          </div>
          <div style={{
            fontFamily: "'Crimson Pro', serif", fontSize: 18, fontWeight: 600,
            color: 'white', lineHeight: 1.25, flex: 1,
          }}>Dialogando com a Doutrina</div>
          {onClose && (
            <button onClick={(e) => { e.stopPropagation(); onClose(); }} style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,.7)', fontSize: 22, lineHeight: 1,
              padding: '0 2px', flexShrink: 0,
            }}>×</button>
          )}
        </div>
        <div style={{
          fontSize: 11, letterSpacing: '.18em', textTransform: 'uppercase',
          color: 'rgba(255,255,255,.45)', paddingLeft: 44, marginTop: 2,
        }}>Estude · Reflita · Compreenda</div>
      </div>

      {/* Nav */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '0 8px 12px' }}>
        <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '4px 4px 10px' }} />
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 8px',
        }}>Modos de estudo</div>

        {navModes.map(m => (
          <div key={m.id}
            onClick={() => onModeChange(m.id)}
            style={{
              ...navBase,
              fontWeight: mode === m.id ? 600 : 400,
              color: mode === m.id ? 'white' : 'rgba(255,255,255,.7)',
              background: mode === m.id ? 'rgba(255,255,255,.22)' : 'transparent',
            }}>
            {m.label}
          </div>
        ))}

        {/* Daily trecho */}
        <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 7px',
        }}>Trecho do dia</div>
        <div
          onClick={evangelhoData ? onStudyTrecho : undefined}
          style={{
            background: 'rgba(0,0,0,.15)', borderRadius: 8, padding: '11px 12px', margin: '0 2px',
            cursor: evangelhoData ? 'pointer' : 'default',
            transition: 'background .15s',
          }}
          onMouseEnter={e => { if (evangelhoData) e.currentTarget.style.background = 'rgba(0,0,0,.25)'; }}
          onMouseLeave={e => { if (evangelhoData) e.currentTarget.style.background = 'rgba(0,0,0,.15)'; }}
        >
          {evangelhoData ? (
            <>
              <div style={{
                fontFamily: "'Crimson Pro', serif", fontSize: 14, fontStyle: 'italic',
                color: 'rgba(255,255,255,.82)', lineHeight: 1.65, marginBottom: 7,
              }}>"{evangelhoData.content.slice(0, 320)}…"</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.4)', lineHeight: 1.5 }}>
                {evangelhoData.source.chapter_title && (
                  <div>{evangelhoData.source.chapter_title}</div>
                )}
                <div>{evangelhoData.source.book}</div>
              </div>
              {evangelhoData.chapter_summary && (
                <div style={{
                  fontSize: 11, fontStyle: 'italic', color: 'rgba(255,255,255,.5)',
                  lineHeight: 1.5, marginTop: 6,
                }}>
                  {evangelhoData.chapter_summary.length > 140
                    ? evangelhoData.chapter_summary.slice(0, 140) + '…'
                    : evangelhoData.chapter_summary}
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,.45)', fontStyle: 'italic' }}>
              Carregando trecho do dia…
            </div>
          )}
        </div>

        {/* Favorited convos */}
        {conversations.some(c => c.favorited) && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Conversas favoritas</div>
            {conversations.filter(c => c.favorited).map(c => (
              <ConvoItem key={c.id} c={c} onLoad={onLoadConvo} onDelete={onDeleteConvo} onToggleFav={onToggleConvoFavorite} />
            ))}
          </>
        )}

        {/* Recent convos */}
        {conversations.some(c => !c.favorited) && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Conversas recentes</div>
            {conversations.filter(c => !c.favorited).slice(0, 8).map(c => (
              <ConvoItem key={c.id} c={c} onLoad={onLoadConvo} onDelete={onDeleteConvo} onToggleFav={onToggleConvoFavorite} />
            ))}
          </>
        )}

        {/* Message favorites */}
        {favorites.length > 0 && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Respostas salvas</div>
            {favorites.slice(0, 5).map(f => (
              <div key={f.id} style={{
                padding: '6px 8px', borderRadius: 5, cursor: 'pointer',
                color: 'rgba(255,255,255,.6)', fontSize: 11, lineHeight: 1.35,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>⭐ {(f.ia || '').slice(0, 42)}…</div>
            ))}
          </>
        )}
      </div>

      {/* Tutorial button */}
      <div style={{ padding: '8px 12px 14px', flexShrink: 0 }}>
        <button onClick={onTutorial} style={{
          width: '100%', background: 'rgba(255,255,255,.18)',
          border: '1px solid rgba(255,255,255,.32)', color: 'white',
          fontSize: 11.5, fontWeight: 500, padding: '8px 10px', borderRadius: 7,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center',
        }}>
          <svg width={12} height={12} viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          Ver tutorial
        </button>
      </div>
    </div>
  );
}

function ConvoItem({ c, onLoad, onDelete, onToggleFav }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4,
      padding: '3px 4px 3px 8px', borderRadius: 5,
      color: 'rgba(255,255,255,.6)', fontSize: 11,
    }}>
      <div onClick={() => onLoad(c)} style={{
        flex: 1, minWidth: 0, cursor: 'pointer', lineHeight: 1.35, fontSize: 12.5,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        padding: '3px 0',
      }}>{c.title}</div>
      <button onClick={() => onToggleFav(c.id)} title={c.favorited ? 'Remover dos favoritos' : 'Favoritar'} style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        fontSize: 12, padding: '2px 3px', flexShrink: 0, lineHeight: 1,
        color: c.favorited ? '#F5C842' : 'rgba(255,255,255,.35)',
      }}>{c.favorited ? '★' : '☆'}</button>
      <button onClick={() => onDelete(c.id)} title="Apagar conversa" style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        padding: '2px 4px', flexShrink: 0, lineHeight: 1,
        color: 'rgba(255,255,255,.4)', fontSize: 14, fontWeight: 400,
      }}>×</button>
    </div>
  );
}
