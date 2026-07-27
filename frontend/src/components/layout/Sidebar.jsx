import React from 'react';

const LEVEL_LABEL = { curioso: 'Iniciante', estudante: 'Intermediário', aprofundado: 'Avançado' };

const BookIcon = ({ size = 17, color = 'white' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);

/**
 * Desktop sidebar (300px wide, sky blue background), also the mobile drawer.
 *
 * History-only. What belongs here is what the reader accumulates — favourites
 * and recent conversations — plus the one control that starts something new.
 * The modes went to the home launcher, and so did the daily passage, which was
 * the last block here that was not the reader's own material.
 *
 * Props:
 *   onNewConvo     — () => void  (opens the home launcher)
 *   onTutorial     — () => void
 *   conversations  — array of {id, title, mode, msgs}
 *   onLoadConvo    — (convo) => void
 */
export default function Sidebar({
  onNewConvo,
  onTutorial,
  conversations = [], onLoadConvo, onDeleteConvo, onToggleConvoFavorite,
  onClose,
  isMobile = false,
}) {
  const hasFavorites = conversations.some(c => c.favorited);
  const hasRecent = conversations.some(c => !c.favorited);

  return (
    <div style={{
      width: '100%', background: '#6B9BB8',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      height: '100%',
    }}>
      {/* Brand */}
      <div style={{ padding: isMobile ? '14px 12px 10px' : '18px 14px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: 'rgba(255,255,255,.18)', border: '1px solid rgba(255,255,255,.26)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <BookIcon size={15} />
          </div>
          <div style={{
            fontFamily: "'Crimson Pro', serif",
            fontSize: isMobile ? 15 : 18, fontWeight: 600,
            color: 'white', lineHeight: 1.25, flex: 1, minWidth: 0,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>Dialogando com a Doutrina</div>
          {onClose && (
            <button onClick={onClose} aria-label="Fechar menu" style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,.7)', fontSize: 22, lineHeight: 1,
              padding: '0 2px', flexShrink: 0,
            }}>×</button>
          )}
        </div>
        {!isMobile && (
          <div style={{
            fontSize: 11, letterSpacing: '.18em', textTransform: 'uppercase',
            color: 'rgba(255,255,255,.45)', paddingLeft: 40, marginTop: 4,
          }}>Estude · Dialogue · Compreenda</div>
        )}
      </div>

      {/* New conversation — desktop only. It goes to the home launcher and
          nowhere else: home is the canonical place to choose a mode, and a
          shortcut menu here would be a second launcher competing with it.
          The mobile drawer is deliberately untouched — mode selection there
          belongs to MobileBottomNav. */}
      {!isMobile && (
        <div style={{ padding: '0 10px 4px' }}>
          {/* Separates the action from the brand above it, using the same rule
              that divides every other section of the sidebar. */}
          <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '4px 2px 12px' }} />
          <button
            onClick={onNewConvo}
            style={{
              display: 'flex', alignItems: 'center', gap: 7, width: '100%',
              background: 'rgba(255,255,255,.18)',
              border: '1px solid rgba(255,255,255,.32)',
              borderRadius: 8, padding: '9px 12px',
              color: 'white', font: 'inherit', fontSize: 13, fontWeight: 600,
              cursor: 'pointer', transition: 'background .15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,.26)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,.18)'; }}
          >
            <span style={{ fontSize: 15, lineHeight: 1 }}>+</span>
            Nova conversa
          </button>
        </div>
      )}

      {/* Conversations */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '0 8px 12px' }}>
        {hasFavorites && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Favoritas</div>
            {conversations.filter(c => c.favorited).map(c => (
              <ConvoItem key={c.id} c={c} onLoad={onLoadConvo} onDelete={onDeleteConvo} onToggleFav={onToggleConvoFavorite} />
            ))}
          </>
        )}

        {hasRecent && (
          <>
            <div style={{ height: 1, background: 'rgba(255,255,255,.12)', margin: '10px 4px' }} />
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '.14em',
              textTransform: 'uppercase', color: 'rgba(255,255,255,.36)', padding: '0 6px 6px',
            }}>Recentes</div>
            {conversations.filter(c => !c.favorited).slice(0, 8).map(c => (
              <ConvoItem key={c.id} c={c} onLoad={onLoadConvo} onDelete={onDeleteConvo} onToggleFav={onToggleConvoFavorite} />
            ))}
          </>
        )}

        {!hasFavorites && !hasRecent && (
          <div style={{ padding: '20px 8px', fontSize: 12, color: 'rgba(255,255,255,.4)', fontStyle: 'italic', textAlign: 'center' }}>
            Nenhuma conversa salva ainda
          </div>
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
      <button onClick={() => onLoad(c)} style={{
        flex: 1, minWidth: 0, cursor: 'pointer', lineHeight: 1.35, fontSize: 12.5,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        padding: '3px 0', textAlign: 'left', background: 'transparent', border: 'none',
        color: 'inherit', font: 'inherit',
      }}>{c.title}</button>
      <button onClick={() => onToggleFav(c.id)} aria-label={c.favorited ? 'Remover dos favoritos' : 'Favoritar'} title={c.favorited ? 'Remover dos favoritos' : 'Favoritar'} style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        fontSize: 12, padding: '2px 3px', flexShrink: 0, lineHeight: 1,
        color: c.favorited ? '#F5C842' : 'rgba(255,255,255,.35)',
      }}>{c.favorited ? '★' : '☆'}</button>
      <button onClick={() => onDelete(c.id)} aria-label="Apagar conversa" title="Apagar conversa" style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        padding: '2px 4px', flexShrink: 0, lineHeight: 1,
        color: 'rgba(255,255,255,.4)', fontSize: 14, fontWeight: 400,
      }}>×</button>
    </div>
  );
}
