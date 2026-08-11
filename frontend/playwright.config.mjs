// O único teste deste projeto que executa JavaScript de verdade.
//
// Sobe DOIS servidores: a API local e o `astro preview` sobre o dist. Os dois
// têm de ser reais — a falha de CORS da Fase 1 só existe entre um navegador e
// um servidor de verdade, e um dublê de API a esconderia por construção.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  // Sem paralelismo: os dois servidores são compartilhados e o conjunto é
  // pequeno. Previsível vale mais que rápido aqui.
  workers: 1,
  // Um `test.only` esquecido reduziria silenciosamente a única verificação
  // deste projeto que executa JavaScript a um único teste, com o CI ainda
  // verde. Em CI isso falha a build em vez de passar por engano.
  forbidOnly: !!process.env.CI,
  // O reporter padrão do Playwright sob CI (`dot`) não escreve relatório
  // nenhum, e o workflow sobe `playwright-report/` como artefato em caso de
  // falha — sem isto o passo do artefato não encontra nada. Este é o único
  // teste que roda o app de verdade; uma falha remota sem artefato é uma
  // falha que ninguém consegue diagnosticar.
  reporter: [['list'], ['html', { open: 'never' }]],
  // Uma corrida de partida contra os dois webServer acima falha a suíte
  // inteira em CI sem segunda chance — já aconteceu uma vez durante a
  // implementação desta guarda. Uma segunda tentativa cobre a flakiness de
  // startup; uma quebra de verdade falha nas duas tentativas igualmente, então
  // isto não mascara falha real, só dá ao servidor a chance de subir.
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://localhost:4321',
    trace: 'on-first-retry',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'uv run fastapi dev src/api/main.py --port 8000',
      cwd: '..',
      url: 'http://localhost:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // `npm run preview` serve o dist construído — o artefato que a Vercel
      // publica, não a fonte. O script `smoke` constrói antes, apontando
      // PUBLIC_API_URL para a API local.
      command: 'npm run preview',
      url: 'http://localhost:4321/',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
