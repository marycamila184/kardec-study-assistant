import React from 'react';
import { OBRAS } from '../../constants/obras';

export default function IntroObras({ theme, onBack }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px' }}>

      {/* Header com voltar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button onClick={onBack} style={{
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: theme.subtext, fontSize: 18, padding: '2px 4px', lineHeight: 1,
        }}>←</button>
        <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 20, fontWeight: 600, color: theme.text }}>
          Sobre as Obras
        </div>
      </div>

      {/* Quem foi Kardec */}
      <div style={{
        background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
        borderRadius: 10, overflow: 'hidden', marginBottom: 24,
      }}>
        {/* Retrato centralizado */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          padding: '22px 18px 16px', borderBottom: `1px solid ${theme.cardBorder}`,
        }}>
          <img
            src="/kardec.jpg"
            alt="Allan Kardec"
            onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
            style={{
              width: 96, height: 96, borderRadius: '50%', objectFit: 'cover',
              border: '3px solid rgba(107,155,184,.4)', marginBottom: 12,
            }}
          />
          <div style={{
            width: 96, height: 96, borderRadius: '50%',
            background: 'rgba(107,155,184,.12)', border: '1px solid rgba(107,155,184,.22)',
            alignItems: 'center', justifyContent: 'center', display: 'none', marginBottom: 12,
          }}>
            <svg width={36} height={36} viewBox="0 0 24 24" fill="none"
              stroke="#6B9BB8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 20, fontWeight: 600, color: theme.text }}>
            Allan Kardec
          </div>
          <div style={{ fontSize: 11.5, color: theme.subtext, marginTop: 3 }}>
            Lyon, 1804 — Paris, 1869
          </div>
          <div style={{ fontSize: 11, color: '#6B9BB8', marginTop: 5, letterSpacing: '.06em' }}>
            PEDAGOGO · ESCRITOR · CODIFICADOR
          </div>
        </div>

        {/* Bio */}
        <div style={{ padding: '16px 18px' }}>
          <p style={{ fontSize: 13.5, color: theme.text, lineHeight: 1.8, margin: '0 0 10px' }}>
            Hippolyte Léon Denizard Rivail foi um pedagogo francês, discípulo do método Pestalozzi,
            dedicado ao ensino e à pesquisa científica desde jovem. Ao investigar os fenômenos de
            mesas girantes que agitavam a Europa nos anos 1850, percebeu algo de mais profundo do
            que simples curiosidade de salão — e decidiu sistematizar os ensinamentos obtidos por
            meio de médiuns de diferentes países, sob o pseudônimo <strong>Allan Kardec</strong>,
            nome de uma suposta existência anterior como druida gaulês.
          </p>
          <p style={{ fontSize: 13.5, color: theme.text, lineHeight: 1.8, margin: '0 0 10px' }}>
            Seu método era rigoroso: reunia respostas de grupos mediúnicos independentes, comparava,
            filtrava contradições e só publicava o que encontrava consenso — aplicando à pesquisa
            espiritual o mesmo espírito científico que aprendera nas ciências naturais. O resultado
            foi uma doutrina coerente, racional e aberta ao progresso.
          </p>
          <p style={{ fontSize: 13.5, color: theme.text, lineHeight: 1.8, margin: '0 0 16px' }}>
            Entre 1857 e 1868 publicou as cinco obras do Pentateuco Espírita, fundou a{' '}
            <em>Revista Espírita</em> (1858) e a Sociedade Parisiense de Estudos Espíritas.
            Faleceu em 31 de março de 1869 — no mesmo dia em que inaugurava a nova sede da Sociedade.
          </p>

          {/* Citação */}
          <div style={{
            padding: '10px 13px', background: 'rgba(107,155,184,.07)',
            borderLeft: '3px solid #6B9BB8', borderRadius: '0 6px 6px 0',
          }}>
            <div style={{
              fontFamily: "'Crimson Pro', serif", fontSize: 15, fontStyle: 'italic',
              color: theme.obraText, lineHeight: 1.65,
            }}>"O Espiritismo não é uma religião, nem uma seita: é uma ciência."</div>
            <div style={{ fontSize: 10, color: theme.subtext, marginTop: 5 }}>— A Gênese, cap. I</div>
          </div>
        </div>
      </div>

      {/* O Pentateuco — Timeline */}
      <div style={{ marginBottom: 20 }}>
        <div style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: '.14em',
          textTransform: 'uppercase', color: theme.subtext, marginBottom: 16,
        }}>O Pentateuco Espírita</div>

        <div style={{ position: 'relative', paddingLeft: 44 }}>
          <div style={{
            position: 'absolute', left: 14, top: 15, bottom: 15,
            width: 2, background: 'rgba(107,155,184,0.35)',
          }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {OBRAS.map((o) => (
              <div key={o.id} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  position: 'absolute', left: 0,
                  width: 30, height: 30, borderRadius: '50%',
                  background: '#6B9BB8',
                  boxShadow: '0 0 0 4px rgba(107,155,184,0.15)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 8.5, fontWeight: 700, color: 'white',
                  zIndex: 1,
                }}>{o.abbr}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                    borderRadius: 8, padding: '11px 13px',
                  }}>
                    <div style={{ fontSize: 10, color: '#6B9BB8', fontStyle: 'italic', marginBottom: 4 }}>{o.year}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: theme.text, marginBottom: 4 }}>{o.label}</div>
                    <div style={{ fontSize: 12, color: theme.subtext, lineHeight: 1.55 }}>{o.summary}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
