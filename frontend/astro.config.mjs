import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// `format: 'directory'` é obrigatório: é ele que produz dist/sobre/index.html
// em vez de dist/sobre.html. As URLs com barra final já estão indexadas pelo
// Google, e mudá-las anula o trabalho que as criou.
//
// `output: 'static'` mantém o deploy exatamente como está: a Vercel serve
// frontend/dist/ e não existe vercel.json neste projeto. Nenhum runtime de
// servidor entra aqui.
export default defineConfig({
  output: 'static',
  build: { format: 'directory' },
  integrations: [react()],
});
