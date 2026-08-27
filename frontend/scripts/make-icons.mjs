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

// `escala` menor que 1 recua a arte para dentro da zona segura.
//
// O Android recorta ícone maskable num círculo de 80% do lado, e o que ficar
// fora some. Como o SVG já tem o retângulo azul de fundo, encolher a arte
// inteira sobre um campo azul do mesmo tom não deixa emenda visível: o que
// o recorte come é azul liso.
const ALVOS = [
  { arquivo: 'icons/icon-192.png',          lado: 192, escala: 1 },
  { arquivo: 'icons/icon-512.png',          lado: 512, escala: 1 },
  { arquivo: 'icons/icon-maskable-512.png', lado: 512, escala: 0.78 },
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
        width: ${lado}px; height: ${lado}px; background: #6B9BB8;
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
