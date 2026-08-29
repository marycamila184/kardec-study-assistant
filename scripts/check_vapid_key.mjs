// Confere que a chave VAPID pública chegou de verdade ao bundle construído.
// Rode com: node scripts/check_vapid_key.mjs (raiz do repo, DEPOIS de
// `cd frontend && npm run build`, no MESMO shell/ambiente usado para o build
// — este script lê PUBLIC_VAPID_KEY do próprio processo, exatamente a
// variável que o build teria lido).
//
// `frontend/src/services/push.js` agora recusa pedir permissão de
// notificação quando PUBLIC_VAPID_KEY está vazia (ver o comentário lá): sem
// essa chave, a inscrição falhava DEPOIS do pedido de permissão, e o
// navegador só pergunta uma vez — a pessoa ficava sem recurso algum. Esta
// guarda cobre o lado do build: se o código fala em PUBLIC_VAPID_KEY, o
// bundle final precisa ter recebido uma chave plausível, não a string vazia
// nem algo malformado.
//
// Por que ler o bundle não bastava sozinho: `if (!VAPID) return {...}` faz o
// Vite substituir `import.meta.env.PUBLIC_VAPID_KEY` por um literal em tempo
// de build, e quando a chave está vazia o Terser resolve a condição em tempo
// de build e ELIMINA o resto da função como código morto — inclusive a
// chamada que usaria a chave. Sem a chave configurada, a string "VAPID" nem
// aparece no bundle final. Isso é o comportamento CORRETO (é exatamente o
// código morto que deveria sumir), mas também significa que procurar só no
// bundle não distingue "ausente" de "presente e malformada" — os dois casos
// podem deixar rastro nenhum. Por isso este script lê o valor real de
// `process.env.PUBLIC_VAPID_KEY`, a mesma fonte que o build usa, para saber
// qual dos dois casos é, e só depois confere que esse valor (quando não
// vazio) realmente chegou ao bundle em vez de ter sido perdido no caminho.
//
// AVISO em vez de FALHA quando a chave está ausente, de propósito: a variável
// `PUBLIC_VAPID_KEY` ainda não está configurada na Vercel neste momento do
// projeto (ver docs/deploy.md), então uma guarda que falhasse por isso
// travaria toda build antes de o lembrete existir de verdade em produção.
// Uma guarda que nunca pode passar não pertence à CI (por isso ela não está
// no ci.yml — ver docs/deploy.md). Ela só FALHA quando a chave existe mas
// está malformada, ou quando existe mas não chegou ao bundle — os dois casos
// em que algo está genuinamente errado, não apenas pendente.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'frontend/dist';
const FONTE_PUSH = 'frontend/src/services/push.js';

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

if (!existsSync(FONTE_PUSH)) {
  console.log(`AVISO ${FONTE_PUSH} não existe — nada a conferir`);
  process.exit(0);
}

const fonteUsaVapid = readFileSync(FONTE_PUSH, 'utf8').includes('PUBLIC_VAPID_KEY');
if (!fonteUsaVapid) {
  console.log(`AVISO ${FONTE_PUSH} não menciona PUBLIC_VAPID_KEY — nada a conferir`);
  process.exit(0);
}

// Base64url: letras, dígitos, '-' e '_', sem padding. 80+ caracteres é
// plausível para o ponto público não comprimido (65 bytes -> ~87 caracteres
// em base64url) sem prender ao tamanho exato.
const CHAVE_PLAUSIVEL = /^[A-Za-z0-9_-]{80,}$/;

const chaveDoAmbiente = process.env.PUBLIC_VAPID_KEY || '';

if (!chaveDoAmbiente) {
  console.log('AVISO PUBLIC_VAPID_KEY não está configurada neste ambiente');
  console.log(
    '   sem ela, o lembrete pede permissão de notificação e a inscrição falha em ' +
      'seguida — e o navegador só pergunta uma vez.'
  );
  process.exit(0);
}

if (!CHAVE_PLAUSIVEL.test(chaveDoAmbiente)) {
  check(
    'PUBLIC_VAPID_KEY tem o formato de uma chave pública VAPID',
    false,
    `valor configurado (${chaveDoAmbiente.length} caracteres) não parece uma chave ` +
      'pública VAPID válida — confira a variável na Vercel.'
  );
  process.exit(1);
}

if (!existsSync(DIST)) {
  console.log(`AVISO ${DIST} não existe`);
  console.log('   rode `cd frontend && npm run build` antes desta guarda');
  process.exit(0);
}

const astroDir = join(DIST, '_astro');
let jsFiles = [];
if (existsSync(astroDir)) {
  const walk = (dir) => {
    for (const nome of readdirSync(dir)) {
      const caminho = join(dir, nome);
      if (statSync(caminho).isDirectory()) walk(caminho);
      else if (nome.endsWith('.js')) jsFiles.push(caminho);
    }
  };
  walk(astroDir);
}

if (jsFiles.length === 0) {
  console.log(`AVISO nenhum .js em ${astroDir} — o build produziu o que se esperava?`);
  process.exit(0);
}

const chaveNoBundle = jsFiles.some((f) => readFileSync(f, 'utf8').includes(chaveDoAmbiente));

check(
  'a chave configurada chegou ao bundle construído',
  chaveNoBundle,
  'PUBLIC_VAPID_KEY está definida e bem formada, mas não aparece em nenhum .js de ' +
    `${astroDir} — o lembrete vai pedir permissão e falhar em seguida.`
);

process.exit(falhou ? 1 : 0);
