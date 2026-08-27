// Confere o manifest, os ícones e os <link> que tornam o site instalável.
// Rode com: node scripts/check_pwa_manifest.mjs
//
// Existe porque toda falha aqui é invisível na tela. Um manifest que não
// chegou ao dist/, um ícone com caminho errado ou um PNG que mente o próprio
// tamanho não quebram nada que se veja: a página abre, o app funciona, a
// pessoa navega — e só o "Instalar app" some do menu, ou o ícone guardado na
// tela de início vira um quadrado cinza. Ninguém que já instalou percebe, e
// quem não instalou não sabe que dava.
//
// É a mesma forma de falha do og:image relativo, que é o motivo de
// check_discovery_assets.mjs existir.
//
// Lê o artefato construído: rode DEPOIS de `npm run build`.
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'frontend/dist';
const MANIFEST = `${DIST}/manifest.webmanifest`;

// O short_name existe para caber embaixo do ícone. Um short_name que é
// truncado não é um short_name — o iPhone corta numa linha só, e o nome
// inteiro ("Dialogando com a Doutrina", 25 caracteres) perde justamente a
// palavra "Doutrina" nos dois sistemas. 12 é o limite prático medido.
const MAX_SHORT_NAME = 12;

// Os dois tamanhos que o Chromium exige para considerar o manifest
// instalável. Faltar um deles não dá erro em lugar nenhum: some o convite.
const TAMANHOS_EXIGIDOS = [192, 512];

if (!existsSync(DIST)) {
  console.log(`FALHA ${DIST} não existe`);
  console.log('   rode `cd frontend && npm run build` antes desta guarda');
  process.exit(1);
}

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

const ler = (caminho) => {
  try {
    return readFileSync(caminho, 'utf8');
  } catch {
    return null;
  }
};

// O tamanho real de um PNG, lido do cabeçalho IHDR: assinatura de 8 bytes,
// depois o comprimento e o tipo do chunk, e a largura e a altura como
// inteiros big-endian de 4 bytes nas posições 16 e 20.
//
// Feito à mão porque uma guarda da raiz não tem dependência nenhuma — e
// porque a alternativa (confiar no nome do arquivo) é exatamente o erro que
// esta checagem existe para pegar.
const dimensoesPng = (caminho) => {
  try {
    const buf = readFileSync(caminho);
    const assinatura = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    if (buf.length < 24 || !buf.subarray(0, 8).equals(assinatura)) return null;
    return { largura: buf.readUInt32BE(16), altura: buf.readUInt32BE(20) };
  } catch {
    return null;
  }
};

// --- o manifest ---
const cru = ler(MANIFEST);
check('frontend/dist/manifest.webmanifest existe', cru !== null,
  'public/ é copiado verbatim pelo Astro — se sumiu aqui, sumiu da fonte');

let manifest = null;
if (cru !== null) {
  try {
    manifest = JSON.parse(cru);
    check('o manifest é JSON válido', true);
  } catch (erro) {
    check('o manifest é JSON válido', false, erro.message);
  }
}

if (manifest) {
  check('tem name', typeof manifest.name === 'string' && manifest.name.length > 0);

  const curto = manifest.short_name;
  check('tem short_name', typeof curto === 'string' && curto.length > 0,
    'sem ele o sistema corta o name inteiro e o leitor não vê "Doutrina"');
  if (typeof curto === 'string') {
    check(`short_name cabe em ${MAX_SHORT_NAME} caracteres`,
      curto.length <= MAX_SHORT_NAME,
      `"${curto}" tem ${curto.length} — vai ser truncado embaixo do ícone`);
  }

  // Sem display: standalone o iOS não trata o site como app de tela de
  // início: abre com a barra do Safari, que é o oposto do pedido.
  check('display é standalone', manifest.display === 'standalone');
  check('start_url é /', manifest.start_url === '/');
  check('scope é /', manifest.scope === '/',
    'scope menor tira /sobre/ e /trilhas/ de dentro do app');
  check('tem background_color', typeof manifest.background_color === 'string');

  // --- os ícones ---
  const icones = Array.isArray(manifest.icons) ? manifest.icons : [];
  check('o manifest declara ícones', icones.length > 0);

  for (const tamanho of TAMANHOS_EXIGIDOS) {
    check(`declara um ícone ${tamanho}x${tamanho} purpose any`,
      icones.some((i) => i.sizes === `${tamanho}x${tamanho}`
        && (i.purpose ?? 'any').split(/\s+/).includes('any')),
      'o Chromium exige 192 e 512 para considerar o manifest instalável');
  }

  check('declara um ícone maskable',
    icones.some((i) => (i.purpose ?? '').split(/\s+/).includes('maskable')),
    'sem ele o Android recorta a arte cheia e come parte do desenho');

  for (const icone of icones) {
    const rel = String(icone.src ?? '').replace(/^\//, '');
    const caminho = join(DIST, rel);
    const existe = existsSync(caminho);
    check(`o ícone ${icone.src} está no dist`, existe);
    if (!existe) continue;

    const dim = dimensoesPng(caminho);
    check(`${icone.src} é um PNG legível`, dim !== null);
    if (!dim) continue;

    // A checagem que o nome do arquivo não faz: um icon-512.png de 192px
    // passa em tudo que olha só para o caminho.
    const [larg, alt] = String(icone.sizes ?? '').split('x').map(Number);
    check(`${icone.src} tem mesmo ${icone.sizes}`,
      dim.largura === larg && dim.altura === alt,
      `o arquivo é ${dim.largura}x${dim.altura}`);
  }
}

// --- o apple-touch-icon e o favicon ---
// O iOS não lê o manifest para o ícone: lê o <link rel="apple-touch-icon">.
// Ele não aparece no JSON acima, então é conferido à parte.
const apple = `${DIST}/apple-touch-icon.png`;
check('apple-touch-icon.png está no dist', existsSync(apple));
if (existsSync(apple)) {
  const dim = dimensoesPng(apple);
  check('o apple-touch-icon é 180x180',
    dim !== null && dim.largura === 180 && dim.altura === 180,
    dim ? `o arquivo é ${dim.largura}x${dim.altura}` : 'não é um PNG legível');
}
check('favicon.svg está no dist', existsSync(`${DIST}/favicon.svg`));

// --- o hex que existe em três lugares ---
// theme_color no manifest, <meta name="theme-color"> no HTML e BRAND_BLUE em
// theme.js. Divergir não quebra nada visível: a barra do sistema fica de uma
// cor e o app de outra, e ninguém que não esteja procurando repara.
const tema = ler('frontend/src/constants/theme.js');
const brand = tema?.match(/BRAND_BLUE\s*=\s*'(#[0-9A-Fa-f]{6})'/)?.[1];
check('theme.js expõe BRAND_BLUE', Boolean(brand));

const index = ler(`${DIST}/index.html`);
const metaTema = index?.match(/<meta\s+name="theme-color"\s+content="(#[0-9A-Fa-f]{6})"/)?.[1];
check('a home tem <meta name="theme-color">', Boolean(metaTema));

if (brand && metaTema && manifest) {
  const iguais = [brand, metaTema, manifest.theme_color]
    .map((c) => String(c).toLowerCase());
  check('theme_color, o meta e BRAND_BLUE são o mesmo hex',
    new Set(iguais).size === 1,
    `manifest=${manifest.theme_color} meta=${metaTema} BRAND_BLUE=${brand}`);
}

// --- os <link> em toda página construída ---
// O manifest só vale onde está linkado. Uma página sem o link é uma porta de
// entrada da qual não dá para instalar — e /trilhas/ e /sobre/ são
// exatamente as páginas que recebem gente vinda de busca e de link
// compartilhado.
const paginas = [];
const varrer = (dir) => {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) varrer(caminho);
    else if (nome.endsWith('.html')) paginas.push(caminho);
  }
};
varrer(DIST);

check('o build produziu páginas HTML', paginas.length > 0);
for (const pagina of paginas) {
  const html = ler(pagina) ?? '';
  const rotulo = pagina.replace(`${DIST}/`, '');
  check(`${rotulo} linka o manifest`,
    /<link[^>]+rel="manifest"/.test(html));
  check(`${rotulo} linka o apple-touch-icon`,
    /<link[^>]+rel="apple-touch-icon"/.test(html));
}

process.exit(falhou ? 1 : 0);
