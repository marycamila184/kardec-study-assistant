// Rasteriza public/favicon.svg nos PNG que o manifest e o iOS pedem.
//
// Rode com: cd frontend && npm run icons
//
// Por que Playwright: não há rsvg-convert, inkscape nem ImageMagick nesta
// máquina, e o Playwright já é devDependency daqui por causa do smoke test.
// Rasterizar num Chromium que já está instalado custa zero dependência nova.
// É por isso também que este script mora em frontend/scripts/ e não em
// scripts/ com as guardas: o Node resolve dependência a partir da pasta do
// arquivo, e as guardas da raiz são de propósito sem dependência nenhuma.
//
// Os PNG são commitados. Este script roda à mão quando a arte muda, nunca em
// CI — o mesmo trato das páginas geradas por src/discovery/.
import { chromium } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
const PUBLIC = join(AQUI, '..', 'public');

const svg = readFileSync(join(PUBLIC, 'favicon.svg'), 'utf8');

// A cor do campo sai do próprio SVG, não de uma constante aqui.
//
// Ela existia escrita à mão como `background: #6B9BB8`, e isso era uma segunda
// cópia do azul — invisível e pior que as outras: trocar o fill do <rect> e
// rodar `npm run icons` produziria um maskable com um anel de 4% da cor VELHA
// em volta da arte nova, e todas as guardas ficariam verdes, porque nenhuma
// delas lê o SVG. Lendo daqui, a arte tem uma cor só por construção.
const COR_CAMPO = svg.match(/<rect[^>]*\sfill="(#[0-9A-Fa-f]{6})"/)?.[1];
if (!COR_CAMPO) {
  console.error('favicon.svg: não achei o fill do <rect> de fundo — a arte mudou de forma?');
  process.exit(1);
}

// `escala` menor que 1 recua a arte para dentro da zona segura.
//
// O Android recorta ícone maskable num círculo de 80% do lado, e o que ficar
// fora some. Como o SVG já tem o retângulo azul de fundo, encolher a arte
// inteira sobre um campo azul do mesmo tom não deixa emenda visível: o que
// o recorte come é azul liso.
//
// O 0.92 é medido, não arbitrado. Com metade do traço (15), a arte ocupa de
// x=97 a x=415 e de y=125 a y=391 num quadro de 512, então o canto dela fica
// a hypot(159, 133) = 207px do centro. A zona segura tem raio 0.4 * 512 =
// 204.8. Ela estoura por 2px — um recuo mínimo resolve, e 0.92 leva o canto
// para 190px, dentro com folga.
//
// A primeira versão usava 0.78, por prudência e sem conta nenhuma. Renderizada
// lado a lado com o recorte do ícone quadrado, o livro aparecia nitidamente
// menor no Android do que em qualquer outro lugar — encolher "por garantia"
// tem custo visível, e aqui era um custo pago por um problema de 2 pixels.
const ALVOS = [
  { arquivo: 'icons/icon-192.png',          lado: 192, escala: 1 },
  { arquivo: 'icons/icon-512.png',          lado: 512, escala: 1 },
  { arquivo: 'icons/icon-maskable-512.png', lado: 512, escala: 0.92 },
  // O iOS não lê o manifest para isto: lê <link rel="apple-touch-icon">. E
  // compõe transparência sobre preto, então o PNG precisa ser opaco — o que
  // ele é, porque o SVG começa com um <rect> que cobre tudo.
  { arquivo: 'apple-touch-icon.png',        lado: 180, escala: 1 },
];

const navegador = await chromium.launch();
const pagina = await navegador.newPage();

for (const { arquivo, lado, escala } of ALVOS) {
  await pagina.setViewportSize({ width: lado, height: lado });
  await pagina.setContent(`<!doctype html>
    <style>
      html, body { margin: 0; padding: 0; }
      .campo {
        width: ${lado}px; height: ${lado}px; background: ${COR_CAMPO};
        display: flex; align-items: center; justify-content: center;
        overflow: hidden;
      }
      .campo svg { width: ${escala * 100}%; height: ${escala * 100}%; display: block; }
    </style>
    <div class="campo">${svg}</div>`);

  const destino = join(PUBLIC, arquivo);
  mkdirSync(dirname(destino), { recursive: true });
  const png = await pagina.locator('.campo').screenshot({ omitBackground: false });
  writeFileSync(destino, png);
  console.log(`${arquivo.padEnd(30)} ${lado}x${lado}${escala < 1 ? '  (maskable)' : ''}`);
}

await navegador.close();
