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
  conversations = [], onLoadConvo,
  favorites = [],
  evangelhoData = null,
}) {
  const navBase = {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '7px 8px', borderRadius: 6, cursor: 'pointer',
    fontSize: 11.5, marginBottom: 2, transition: 'background .15s',
  };

  return (
    <div style={{
      width: 300, background: '#6B9BB8',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{ padding: '18px 14px 8px' }}>
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
            color: 'white', lineHeight: 1.25,
          }}>Dialogando com a Doutrina</div>
        </div>
        <div style={{
          fontSize: 8.5, letterSpacing: '.18em', textTransform: 'uppercase',
          color: 'rgba(255,255,255,.45)', paddingLeft: 44, marginTop: 2,
        }}>Estude · Reflita · Compreenda</div>
      </div>

      {/* Nav */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '0 8px 12px' }}>
        <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '4px 4px 10px' }} />
        <div style={{
          fontSize: 7.5, fontWeight: 700, letterSpacing: '.14em',
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
          fontSize: 7.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 7px',
        }}>Trecho do dia</div>
        <div style={{
          background: 'rgba(0,0,0,.15)', borderRadius: 8, padding: '11px 12px', margin: '0 2px',
        }}>
          {evangelhoData ? (
            <>
              <div style={{
                fontFamily: "'Crimson Pro', serif", fontSize: 12.5, fontStyle: 'italic',
                color: 'rgba(255,255,255,.82)', lineHeight: 1.65, marginBottom: 7,
              }}>"{evangelhoData.content.slice(0, 180)}…"</div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,.4)', marginBottom: 8 }}>
                {evangelhoData.source.book}
                {evangelhoData.source.chapter_title ? ` · ${evangelhoData.source.chapter_title}` : ''}
              </div>
              <button onClick={onStudyTrecho} style={{
                background: 'rgba(255,255,255,.12)', border: '1px solid rgba(255,255,255,.2)',
                color: 'rgba(255,255,255,.78)', fontSize: 10, padding: '4px 10px',
                borderRadius: 12, cursor: 'pointer',
              }}>Estudar este trecho →</button>
            </>
          ) : (
            <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,.45)', fontStyle: 'italic' }}>
              Carregando trecho do dia…
            </div>
          )}
        </div>

        {/* Recent convos */}
        {conversations.length > 0 && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 7.5, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Conversas recentes</div>
            {conversations.slice(0, 8).map(c => (
              <div key={c.id} onClick={() => onLoadConvo(c)} style={{
                padding: '6px 8px', borderRadius: 5, cursor: 'pointer',
                color: 'rgba(255,255,255,.6)', fontSize: 11, lineHeight: 1.35,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{c.title}</div>
            ))}
          </>
        )}

        {/* Favorites */}
        {favorites.length > 0 && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 7.5, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Favoritos</div>
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
