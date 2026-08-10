import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// `format: 'directory'` é obrigatório: é ele que produz dist/sobre/index.html
// em vez de dist/sobre.html. As URLs com barra final já estão indexadas pelo
// Google, e mudá-las anula o trabalho que as criou.
//
// `output: 'static'` mantém o deploy exatamente como está: a Vercel serve
// frontend/dist/ e não existe vercel.json neste projeto. Nenhum runtime de
// servidor entra aqui.
// `compressHTML: false` porque o compressor do Astro colapsa a quebra de linha
// entre um texto e uma tag inline para NADA, em vez de para um espaço. Medido
// em 2026-08-09 na página Sobre: a fonte tinha `está em\n<strong>Configurações`
// e o build produzia `está em<strong>Configurações`, que o leitor vê como
// "está emConfigurações". Três ocorrências, todas em prosa que uma pessoa
// escreveu. O ganho de bytes não paga uma página com palavras grudadas.
//
// `server.port` fixo porque o backend precisa saber a origem para o CORS, e uma
// porta que muda sozinha vira um 400 no preflight sem explicação — foi o que
// aconteceu quando o Vite (5173) virou Astro e o default do backend ficou para
// trás. Ver cors_allowed_origins em src/core/config.py.
export default defineConfig({
  output: 'static',
  build: { format: 'directory' },
  compressHTML: false,
  server: { port: 4321 },
  integrations: [react()],
});
