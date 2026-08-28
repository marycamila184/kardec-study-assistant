// Confere que o service worker do push continua sendo só do push.
// Rode com: node scripts/check_push_service_worker.mjs
//
// A spec do PWA decidiu não ter service worker, medindo que os assets já vêm
// `immutable` da Vercel e que o que um SW acrescentaria era a capacidade de
// fixar versão velha no aparelho em silêncio. O push obriga a ter um. As duas
// coisas convivem por um motivo estrutural e não por cuidado: um worker sem
// handler de `fetch` não pode servir nada velho, porque não serve nada.
//
// Esta guarda existe para que isso continue verdade. Um `fetch` aqui não
// quebraria teste nenhum e não apareceria na tela — reintroduziria em
// silêncio exatamente o risco que a outra spec recusou.
import { existsSync, readFileSync } from 'node:fs';

const SW = 'frontend/public/sw.js';
const CONTATO = 'frontend/src/constants/contact.js';

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

check(`${SW} existe`, existsSync(SW));

if (existsSync(SW)) {
  const sw = readFileSync(SW, 'utf8');
  check('o worker não escuta fetch',
    !/addEventListener\(\s*['"]fetch['"]/.test(sw),
    'um handler de fetch devolve ao worker a capacidade de servir versão velha');
  check('o worker não usa caches',
    !/\bcaches\b/.test(sw),
    'cache aqui é a falha silenciosa que a spec do PWA recusou');
  check('o worker escuta push', /addEventListener\(\s*['"]push['"]/.test(sw));
  check('o worker escuta notificationclick',
    /addEventListener\(\s*['"]notificationclick['"]/.test(sw));
}

// A cópia de privacidade tem de ter andado antes do store existir. Se
// src/push/ está no repositório, PRIVACY_NOTICE tem de falar do lembrete —
// senão o código promete menos do que faz, que é a única direção proibida.
if (existsSync('src/push/store.py')) {
  const copia = existsSync(CONTATO) ? readFileSync(CONTATO, 'utf8') : '';
  check('PRIVACY_NOTICE menciona o lembrete',
    /lembrete/i.test(copia),
    'o store existe em código e a cópia não o anuncia');
}

process.exit(falhou ? 1 : 0);
