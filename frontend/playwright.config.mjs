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
  use: {
    baseURL: 'http://localhost:4321',
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
