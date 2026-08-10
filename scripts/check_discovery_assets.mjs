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

// A guarda lê o artefato construído, não a fonte.
//
// Desde a migração para Astro a fonte é um template (.astro), e as meta tags
// só existem como HTML depois do build. Conferir o que a Vercel realmente
// serve é mais forte do que conferir o que a gente escreveu — mas custa uma
// dependência de ordem: `npm run build` antes desta guarda, sempre.
const DIST = 'frontend/dist';

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

// As frases vivem em frontend/src/content/frases.json e alimentam a home e a
// Sobre (ambas Astro). Lidas uma vez aqui e reusadas nas duas checagens
// abaixo.
const frases = JSON.parse(
  readFileSync('frontend/src/content/frases.json', 'utf8'));

// --- index.html: as meta tags e o corpo estático ---
const index = ler(`${DIST}/index.html`);
check(`${DIST}/index.html existe`, index !== null);

if (index) {
  // O bloco #conteudo-estatico é o único texto que um buscador lê nesta
  // rota: a island é client:only, então o Astro não emite nada do app no
  // HTML. Apagar o bloco, renomear uma chave de frases.json ou perder uma
  // expressão no meio de uma edição de estilo derruba a home de volta para
  // uma página sem corpo — em silêncio, com todo o resto verde.
  check('a home tem <title> com "IA"', /<title>[^<]*IA[^<]*<\/title>/.test(index));
  check('a home tem o bloco id="conteudo-estatico"',
    index.includes('id="conteudo-estatico"'));
  for (const [chave, valor] of Object.entries(frases)) {
    check(`a home tem a frase "${chave}" de frases.json`,
      index.includes(valor), `frase ausente: ${valor}`);
  }

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
const PNG = `${DIST}/preview.png`;
let png = null;
try {
  png = readFileSync(PNG);
} catch {
  /* ausente — o check abaixo reporta */
}
check(`${DIST}/preview.png existe`, png !== null);

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
const sobre = ler(`${DIST}/sobre/index.html`);
check(`${DIST}/sobre/index.html existe`, sobre !== null);

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

  // A Sobre virou frontend/src/pages/sobre.astro e passou a ler as frases de
  // frases.json (`{frases.chave}`) em vez de copiar o texto à mão. O teste
  // Python (tests/test_discovery_render.py) confere que a FONTE referencia o
  // JSON — mas isso não prova que o Astro realmente interpola o valor: uma
  // chave renomeada, uma falha silenciosa de interpolação ou uma edição de
  // template que derruba a expressão passariam por aquele teste e ainda
  // assim publicariam uma Sobre sem a própria frase. Esta guarda lê o HTML
  // CONSTRUÍDO e confere o texto de verdade — comportamental onde a outra é
  // estrutural, e juntas cobrem os dois sentidos.
  for (const [chave, valor] of Object.entries(frases)) {
    check(`a página Sobre tem a frase "${chave}" de frases.json`,
      sobre.includes(valor), `frase ausente: ${valor}`);
  }

  // A página Sobre destrava o overflow:hidden que globals.css põe em
  // html/body para o app, com uma regra `:global(html), :global(body)` de
  // mesma especificidade. Ela só vence porque o Astro emite o CSS global
  // importado ANTES do bloco <style> da página — comportamento documentado,
  // mas não garantido por nada além da ordem de emissão. Se uma migração de
  // integração inverter essa ordem, a última declaração de overflow dentro
  // da regra html,body vira "hidden" e a página trava no primeiro scroll,
  // sem quebrar nenhum outro sinal visível. Esta checagem lê o CSS
  // construído e falha se a ORDEM se inverter.
  // Há DUAS regras "html,body" no CSS construído: a de globals.css (hidden,
  // para o app) e a desta página (auto). Mesma especificidade — quem vence é
  // a que aparece por último no documento. Por isso a checagem varre TODAS
  // as regras html,body em ordem e olha a última declaração overflow entre
  // todas elas, não só a da primeira regra que casar.
  const regrasHtmlBody = [...sobre.matchAll(/html\s*,\s*body\s*\{([^}]*)\}/g)];
  if (regrasHtmlBody.length > 0) {
    const declaracoesOverflow = regrasHtmlBody
      .flatMap(m => [...m[1].matchAll(/overflow\s*:\s*([a-z]+)/g)].map(d => d[1]));
    const ultima = declaracoesOverflow[declaracoesOverflow.length - 1] ?? null;
    check('a última declaração overflow entre as regras html,body é "auto"',
      ultima === 'auto',
      `obtido: ${ultima} (declarações, em ordem: ${declaracoesOverflow.join(', ')})`);
  } else {
    check('a página Sobre tem uma regra html,body no CSS construído', false);
  }
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
const robots = ler(`${DIST}/robots.txt`);
check(`${DIST}/robots.txt existe`, robots !== null);
if (robots) {
  check('robots.txt aponta para o sitemap',
    robots.includes(`Sitemap: ${HOST}/sitemap.xml`));
}

const sitemap = ler(`${DIST}/sitemap.xml`);
check(`${DIST}/sitemap.xml existe`, sitemap !== null);
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
  const raiz = `${DIST}/${familia}`;
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

    if (familia === 'trilhas') {
      // Desde a Fase 2 esta página É o app: a island monta na mesma URL que o
      // buscador leu. O que substituiu a regra do "<script> proibido" é mais
      // forte que ela — o texto tem de estar no HTML SERVIDO — e é o que as
      // duas checagens abaixo exigem. Sem elas, uma rota que emitisse só a
      // island passaria: página válida, app funcionando, e um rastreador
      // vendo uma div vazia.
      check(`${familia}/${slug} monta o app`, /<script[\s>]/i.test(html));
      check(`${familia}/${slug} tem o bloco id="conteudo-estatico"`,
        html.includes('id="conteudo-estatico"'));

      const conteudo = ler(`frontend/src/content/trilhas/${slug}.json`);
      check(`frontend/src/content/trilhas/${slug}.json existe`, conteudo !== null,
        'rode: uv run python -m src.discovery.generate');
      if (conteudo) {
        // O HTML escapa &, <, > e as aspas; desfazer isso é o que permite
        // comparar o texto do trecho literalmente, em vez de por um pedaço
        // curto que um truncamento silencioso ainda passaria.
        const servido = html
          .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
          .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
          .replace(/&amp;/g, '&');
        const trilha = JSON.parse(conteudo);
        const ausentes = trilha.passages
          .filter((p) => !servido.includes(p.text))
          .map((p) => p.label);
        check(`${familia}/${slug}: todo trecho está no HTML servido`,
          ausentes.length === 0, `ausentes: ${ausentes.join(', ')}`);

        // Deliberadamente adormecida hoje: nenhuma das seis trilhas curadas
        // tem uma passagem com `part` (nenhuma vem de O Céu e o Inferno), então
        // este laço não roda nenhuma vez em nenhum build atual. Existe porque
        // a checagem em Python que cobria isso (test_deep_link_carries_the_part
        // / test_deep_link_omits_an_absent_part, tests/test_discovery_render.py)
        // guarda o `deep_link` de render.py, que desde a Fase 2 só serve
        // temas — zero deles existem hoje. O deep link que a rota Astro
        // realmente serve (deepLink em [slug].astro) ficou sem nenhuma
        // checagem. Sem `part`, O Céu e o Inferno reinicia a numeração por
        // parte e um deep link que o perde resolve, em silêncio, para a
        // passagem errada (O PASSAMENTO em vez de O PORVIR E O NADA, por
        // exemplo) — e nada na aplicação em execução expõe isso. Acende
        // sozinha no dia em que uma trilha curada ganhar um passo de O Céu e
        // o Inferno.
        for (const p of trilha.passages) {
          if (!p.part) continue;
          // Mesma codificação que URLSearchParams produz em deepLink(): o
          // espaço em "I PARTE" vira "+", não "%20".
          const partParam = new URLSearchParams({ part: p.part }).toString();
          check(`${familia}/${slug}: o deep link de "${p.label}" carrega part`,
            servido.includes(partParam), `esperado "${partParam}" ausente do HTML`);
        }
      }
    } else {
      // Um tema continua sendo página estática gerada pelo Python, sem app.
      check(`${familia}/${slug} não tem JavaScript`, !/<script/i.test(html));
    }
    check(`${familia}/${slug} tem canonical próprio, com barra final`,
      html.includes(`<link rel="canonical" href="${url}">`));
    check(`${familia}/${slug} tem og:url igual ao canonical`,
      html.includes(`<meta property="og:url" content="${url}">`));
    check(`${familia}/${slug} não aponta para a URL da Vercel`,
      !html.includes('kardec-study-assistant.vercel.app'));
    // `[\s>]` em vez de exigir `<h1>` exato: a rota de trilha tem <style>
    // escopado, e o Astro grava um atributo data-astro-cid-* em cada tag do
    // componente — as páginas de tema, ainda em Python puro, seguem batendo
    // com a forma exata.
    check(`${familia}/${slug} tem <h1>`, /<h1[\s>]/i.test(html));

    // As portas: o motivo de a página ser uma entrada e não um beco. Somem
    // numa edição de estilo sem quebrar nada visível.
    check(`${familia}/${slug} tem a porta do Dialogar`,
      html.includes(`href="${HOST}/?mode=duvida"`));

    // O cabeçalho: quem chega de uma busca não sabe o que é este site, e a
    // única página que explica está a um link de rodapé de distância.
    check(`${familia}/${slug} tem o cabeçalho do projeto`,
      html.includes('class="cabecalho"'));
    check(`${familia}/${slug} diz o que o projeto é`,
      html.includes('Um assistente de estudo das obras de Allan Kardec.'));
    // A checagem acima passaria com só a primeira frase, se a segunda fosse
    // cortada em silêncio — esta pega o rabo dela.
    check(`${familia}/${slug} diz que a resposta vem com a fonte`,
      html.includes('o número da questão ou do item.'));
    check(`${familia}/${slug} avisa que pode errar`,
      html.includes('Ele pode errar.'));

    // Exatamente um trecho aberto. Zero é uma página que parece vazia; dois
    // desfazem metade do motivo de recolher.
    // \bopen\b em vez de exigir `open>` colado: mesmo motivo do <h1> acima —
    // o data-astro-cid-* do Astro entra entre "open" e o fechamento da tag.
    const abertos = (html.match(/<details class="passagem"[^>]*\bopen\b[^>]*>/g) || []).length;
    check(`${familia}/${slug} tem exatamente um trecho aberto`,
      abertos === 1, `obtido: ${abertos}`);

    // Um <details> por trecho: o link "Abrir no app" é emitido uma vez por
    // trecho, então os dois números têm de bater. Pega um trecho que perdeu
    // o seu invólucro numa edição de estilo.
    const detalhes = (html.match(/<details class="passagem"/g) || []).length;
    const links = (html.match(/class="abrir"/g) || []).length;
    check(`${familia}/${slug}: um trecho recolhido por link de abrir`,
      detalhes === links && detalhes > 0, `details: ${detalhes}, links: ${links}`);

    if (familia === 'trilhas') {
      check(`${familia}/${slug} tem a porta da trilha, com o slug do diretório`,
        html.includes(`href="${HOST}/?trilha=${slug}"`));
      // O botão Estudar só funciona enquanto o slug for o id da trilha.
      // Renomear um data/paths/*.json e regenerar produz uma página perfeita
      // com um botão que cai no picker — falha silenciosa clássica aqui.
      check(`data/paths/${slug}.json existe (o botão Estudar depende do id)`,
        existsSync(`data/paths/${slug}.json`));
    } else {
      check(`${familia}/${slug} (tema) não oferece ?trilha=`,
        !html.includes('?trilha='));
    }
  }
}

check('há pelo menos uma página gerada', paginasGeradas.length > 0,
  'rode: uv run python -m src.discovery.generate');

// Uma trilha curada cujo JSON existe mas cuja página não foi construída é uma
// URL indexada virando 404 — e getStaticPaths() falhando em silêncio para um
// arquivo é exatamente a forma que isso teria.
const conteudoTrilhas = 'frontend/src/content/trilhas';
if (existsSync(conteudoTrilhas)) {
  for (const arquivo of readdirSync(conteudoTrilhas)) {
    if (!arquivo.endsWith('.json')) continue;
    const slug = arquivo.replace(/\.json$/, '');
    check(`a trilha curada ${slug} tem página construída`,
      existsSync(`${DIST}/trilhas/${slug}/index.html`));
  }
}

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
      existsSync(`${DIST}/${relativo}index.html`));
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
  check('App.jsx lê o parâmetro de trilha', app.includes("params.get('trilha')"));
  check('App.jsx lê o parâmetro de modo', app.includes("params.get('mode')"));
  // Ler o parâmetro não basta: a versão que esta guarda deixou passar lia
  // ?trilha= e chamava startTrilha sem entrar em Estudar, então a trilha
  // carregava por baixo da tela inicial. Prende o parâmetro à ação.
  check('a trilha do deep link entra no modo estudar e começa a trilha',
    /trilhaId[\s\S]{0,400}switchMode\('estudar'\)[\s\S]{0,400}startTrilha\(/.test(app));
  check('o modo do deep link chama switchMode',
    /modeParam ===[\s\S]{0,200}switchMode\(modeParam\)/.test(app));
}

process.exit(falhou ? 1 : 0);
