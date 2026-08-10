// Abre a página construída, deixa o JavaScript rodar e confere que a trilha
// chega na tela vinda da API.
//
// A Fase 1 publicou duas falhas. Esta suíte cobre uma delas: o CORS mal
// configurado, que só existe entre um navegador de verdade e um servidor de
// verdade, e que nenhuma outra verificação deste projeto podia ver — o
// `npm run build` aceita qualquer string, as guardas leem HTML, o pytest é
// do backend e o curl nunca roda script. A outra falha — `PUBLIC_API_URL`
// gravado no bundle de produção — este arquivo NÃO cobre, por construção:
// `npm run smoke` constrói apontando PUBLIC_API_URL para a API local, então
// "localhost" aqui dentro é o comportamento esperado. Essa falha é do
// `scripts/check_api_base.mjs`, rodado contra um build de produção.
//
// O que este arquivo também NÃO cobre, de propósito: a resposta do /study,
// que precisa do índice ChromaDB (gitignorado) e de chave de LLM. As
// asserções abaixo param na costura navegador↔API.
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const SLUG = 'fundamentos-evangelico-curioso';

// Lido de data/paths/, não escrito à mão: o rótulo e a contagem de passos
// mudam quando a curadoria muda, e um número fixo aqui viraria uma falha
// sobre a trilha ter sido editada, não sobre o app ter quebrado.
const trilha = JSON.parse(
  readFileSync(new URL(`../../data/paths/${SLUG}.json`, import.meta.url), 'utf8'),
);

test('a rota de trilha entrega a trilha ao app, pela API', async ({ page }) => {
  const respostas = [];
  page.on('response', (r) => respostas.push([r.url(), r.status()]));
  const erros = [];
  page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
  page.on('requestfailed', (r) => erros.push(`${r.url()} — ${r.failure()?.errorText}`));

  // Montar a trilha dispara uma chamada a /study/stream que não pode dar
  // certo aqui — não há índice ChromaDB nem chave de LLM em CI. Isso é
  // esperado e inofensivo: nenhuma asserção depende do resultado dela, e é
  // essa chamada (com sucesso ou caindo no catch) que eventualmente produz a
  // segunda ocorrência do rótulo do passo que o `.first()` abaixo existe
  // para tolerar.
  await page.goto(`/trilhas/${SLUG}/`);

  // A island montou: o bloco estático existia no HTML e o app o removeu.
  await expect(page.locator('#conteudo-estatico')).toHaveCount(0, { timeout: 15_000 });

  // O passo 1 na tela só aparece depois de GET /paths/<slug> voltar 200: o
  // rótulo e a contagem vêm da resposta, não do HTML.
  //
  // `.first()`: assim que a chamada a /study/stream (disparada logo abaixo)
  // resolve — com sucesso num ambiente completo, ou na mensagem de erro do
  // catch em CI — o rótulo do passo aparece uma segunda vez na tela, e sem
  // `.first()` isso é uma violação de strict mode, não uma falha limpa.
  await expect(page.getByText(trilha.steps[0].label).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(`1 de ${trilha.steps.length}`)).toBeVisible();

  const paths = respostas.find(([url]) => url.endsWith(`/paths/${SLUG}`));
  expect(paths, 'nenhuma chamada a /paths/<slug> saiu do navegador').toBeTruthy();
  expect(paths[1]).toBe(200);

  // Um CORS mal configurado não derruba a página: ele derruba a chamada, e o
  // navegador reporta no console. A asserção acima já falharia, mas o texto do
  // erro é o que diz POR QUE.
  expect(erros.filter((e) => /CORS|Failed to fetch|NetworkError/i.test(e))).toEqual([]);
});

test('nenhuma chamada sai para um host que não seja a API configurada', async ({ page }) => {
  const hosts = new Set();
  page.on('request', (r) => hosts.add(new URL(r.url()).host));
  await page.goto(`/trilhas/${SLUG}/`);
  await expect(page.locator('#conteudo-estatico')).toHaveCount(0, { timeout: 15_000 });

  // fonts.googleapis.com e fonts.gstatic.com são as fontes do <head>. Qualquer
  // outro host de terceiro aqui é uma chamada que ninguém pediu.
  const inesperados = [...hosts].filter(
    (h) => !['localhost:4321', 'localhost:8000', 'fonts.googleapis.com', 'fonts.gstatic.com'].includes(h),
  );
  expect(inesperados).toEqual([]);
});

test.describe('sem JavaScript', () => {
  test.use({ javaScriptEnabled: false });

  test('o texto dos trechos está no HTML servido', async ({ page }) => {
    await page.goto(`/trilhas/${SLUG}/`);
    // O invariante que substituiu a regra do "<script> proibido", medido do
    // único jeito que importa: num navegador que não executa script.
    await expect(page.locator('#conteudo-estatico')).toBeVisible();
    await expect(page.getByText(trilha.steps[0].label).first()).toBeVisible();
    await expect(page.locator('details.passagem')).toHaveCount(trilha.steps.length);
  });
});
