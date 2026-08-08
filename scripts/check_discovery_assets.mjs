// Sem runner de testes no frontend: este script confere os assets de descoberta
// (meta tags, imagem de preview, página Sobre, robots e sitemap).
// Rode com: node scripts/check_discovery_assets.mjs
//
// Existe porque toda falha aqui é silenciosa. Um og:image relativo, um canonical
// ausente ou um PNG de 400 KB não quebram nada visível: a página abre normal e
// só o card compartilhado sai vazio — e o WhatsApp cacheia isso com força.
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';

const HOST = 'https://dialogandodoutrina.com.br';
const MAX_PNG_BYTES = 300 * 1024;

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

// --- index.html: as meta tags ---
const index = ler('frontend/index.html');
check('frontend/index.html existe', index !== null);

if (index) {
  const tag = (nome, attr = 'property') =>
    index.match(new RegExp(`<meta\\s+${attr}="${nome}"\\s+content="([^"]*)"`, 'i'))?.[1] ?? null;

  check('tem <meta name="description">', !!tag('description', 'name'));
  check('og:title presente', !!tag('og:title'));
  check('og:description presente', !!tag('og:description'));
  check('og:locale é pt_BR', tag('og:locale') === 'pt_BR');
  check('twitter:card é summary_large_image',
    tag('twitter:card', 'name') === 'summary_large_image');

  const ogUrl = tag('og:url');
  check('og:url é o domínio próprio, com barra final',
    ogUrl === `${HOST}/`, `obtido: ${ogUrl}`);

  const ogImage = tag('og:image');
  check('og:image é URL absoluta no domínio próprio',
    ogImage === `${HOST}/preview.png`, `obtido: ${ogImage}`);

  const canonical = index.match(/<link\s+rel="canonical"\s+href="([^"]*)"/i)?.[1] ?? null;
  check('canonical aponta para o domínio próprio',
    canonical === `${HOST}/`, `obtido: ${canonical}`);

  check('theme-color é o azul da marca',
    tag('theme-color', 'name') === '#6B9BB8');

  // O domínio da Vercel serve o mesmo app. Se ele aparecer numa tag, o buscador
  // indexa duas cópias e divide o sinal entre elas.
  check('nenhuma tag aponta para a URL da Vercel',
    !index.includes('kardec-study-assistant.vercel.app'));
}

// --- preview.png: dimensões e peso ---
// Lê o cabeçalho IHDR do PNG: largura e altura são big-endian nos bytes 16..24.
const PNG = 'frontend/public/preview.png';
let png = null;
try {
  png = readFileSync(PNG);
} catch {
  /* ausente — o check abaixo reporta */
}
check('frontend/public/preview.png existe', png !== null);

if (png) {
  const largura = png.readUInt32BE(16);
  const altura = png.readUInt32BE(20);
  check('preview.png é 1200x630', largura === 1200 && altura === 630,
    `obtido: ${largura}x${altura}`);
  const bytes = statSync(PNG).size;
  check(`preview.png cabe em ${MAX_PNG_BYTES} bytes`, bytes <= MAX_PNG_BYTES,
    `obtido: ${bytes} bytes — o WhatsApp ignora imagem grande`);
}

// --- a página Sobre ---
const sobre = ler('frontend/public/sobre/index.html');
check('frontend/public/sobre/index.html existe', sobre !== null);

if (sobre) {
  // O ponto inteiro da página é ser lida antes de qualquer bundle carregar.
  check('a página Sobre não tem JavaScript', !/<script/i.test(sobre));
  check('a página Sobre cita as cinco obras',
    ['O Livro dos Espíritos', 'O Livro dos Médiuns',
     'O Evangelho Segundo o Espiritismo', 'O Céu e o Inferno',
     'A Gênese'].every(o => sobre.includes(o)));
  check('o contato é o formulário, não um e-mail',
    sobre.includes('docs.google.com/forms') && !/mailto:/i.test(sobre));
  check('a página Sobre tem canonical próprio',
    sobre.includes(`href="${HOST}/sobre/"`));
  check('og:url da página Sobre também tem barra final',
    sobre.includes(`property="og:url" content="${HOST}/sobre/"`));
}

// --- os links internos para /sobre/: a barra final tem que sobreviver aqui
// também. O bug que isto pega é uma edição de "faxina" — trocar
// href="/sobre/" por href="/sobre" parece um ajuste inofensivo e não quebra
// nada visível: o link abre o app (SPA) em vez da página estática, do mesmo
// jeito que scripts/check_chat_current_mode.mjs existe para pegar
// current_mode esquecido.
const sidebar = ler('frontend/src/components/layout/Sidebar.jsx');
check('frontend/src/components/layout/Sidebar.jsx existe', sidebar !== null);
if (sidebar) {
  check('Sidebar.jsx aponta para /sobre/, com barra final',
    sidebar.includes('href="/sobre/"'));
}

const settingsPanel = ler('frontend/src/components/modals/SettingsPanel.jsx');
check('frontend/src/components/modals/SettingsPanel.jsx existe', settingsPanel !== null);
if (settingsPanel) {
  check('SettingsPanel.jsx aponta para /sobre/, com barra final',
    settingsPanel.includes('href="/sobre/"'));
}

// --- robots e sitemap ---
const robots = ler('frontend/public/robots.txt');
check('frontend/public/robots.txt existe', robots !== null);
if (robots) {
  check('robots.txt aponta para o sitemap',
    robots.includes(`Sitemap: ${HOST}/sitemap.xml`));
}

const sitemap = ler('frontend/public/sitemap.xml');
check('frontend/public/sitemap.xml existe', sitemap !== null);
if (sitemap) {
  check('sitemap lista a home', sitemap.includes(`<loc>${HOST}/</loc>`));
  check('sitemap lista /sobre/', sitemap.includes(`<loc>${HOST}/sobre/</loc>`));
}

// --- as páginas geradas: temas e trilhas ---
// Geradas por src/discovery/generate.py e commitadas. Os dois sentidos
// importam: uma página fora do sitemap não é encontrada, e uma entrada do
// sitemap sem arquivo é um 404 que só o buscador vê.
const paginasGeradas = [];
for (const familia of ['temas', 'trilhas']) {
  const raiz = `frontend/public/${familia}`;
  if (!existsSync(raiz)) {
    // temas/ só existe quando houver algum tema curado; trilhas/ é obrigatório.
    if (familia === 'trilhas') {
      check(`${raiz} existe`, false, 'rode: uv run python -m src.discovery.generate');
    }
    continue;
  }
  for (const slug of readdirSync(raiz)) {
    const caminho = `${raiz}/${slug}/index.html`;
    const url = `${HOST}/${familia}/${slug}/`;
    const html = ler(caminho);
    check(`${caminho} existe`, html !== null);
    if (!html) continue;
    paginasGeradas.push(url);

    // O motivo inteiro destas páginas existirem: texto antes de qualquer
    // bundle, e conteúdo para quem não executa JavaScript.
    check(`${familia}/${slug} não tem JavaScript`, !/<script/i.test(html));
    check(`${familia}/${slug} tem canonical próprio, com barra final`,
      html.includes(`<link rel="canonical" href="${url}">`));
    check(`${familia}/${slug} tem og:url igual ao canonical`,
      html.includes(`<meta property="og:url" content="${url}">`));
    check(`${familia}/${slug} não aponta para a URL da Vercel`,
      !html.includes('kardec-study-assistant.vercel.app'));
    check(`${familia}/${slug} tem <h1>`, /<h1>/i.test(html));
  }
}

check('há pelo menos uma página gerada', paginasGeradas.length > 0,
  'rode: uv run python -m src.discovery.generate');

if (sitemap) {
  for (const url of paginasGeradas) {
    check(`sitemap lista ${url}`, sitemap.includes(`<loc>${url}</loc>`));
  }
  // O sentido inverso: entrada sem arquivo é 404 silencioso.
  const noSitemap = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
  for (const url of noSitemap) {
    const relativo = url.replace(`${HOST}/`, '');
    if (!relativo.startsWith('temas/') && !relativo.startsWith('trilhas/')) continue;
    check(`a entrada ${url} tem arquivo`,
      existsSync(`frontend/public/${relativo}index.html`));
  }
}

// --- o leitor do deep link ---
// O deep link é o que faz das páginas estáticas uma porta em vez de um beco:
// sem este leitor elas só conseguem apontar para "/" e o leitor perde a
// passagem que estava lendo. Some numa "faxina" sem quebrar nada visível.
const app = ler('frontend/src/App.jsx');
check('frontend/src/App.jsx existe', app !== null);
if (app) {
  check('App.jsx lê os parâmetros do deep link',
    app.includes('URLSearchParams') && app.includes("params.get('item')"));
  check('o deep link carrega part', app.includes("params.get('part')"));
}

process.exit(falhou ? 1 : 0);
