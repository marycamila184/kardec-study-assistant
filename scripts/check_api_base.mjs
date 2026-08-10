// Confere que o bundle construído não fala com a máquina de quem visita.
//
// Existe por uma falha que ficou no ar: `services/api.js` lia
// `import.meta.env.VITE_API_URL`, com fallback para `http://localhost:8000`. O
// Vite expõe ao cliente as variáveis com prefixo VITE_; o Astro expõe as com
// prefixo PUBLIC_. Depois da migração a variável passou a ser `undefined`, o
// fallback venceu, e `localhost:8000` foi publicado dentro do bundle.
//
// O que isso faz com quem abre o site: nenhuma trilha carrega, nenhuma resposta
// chega, e o navegador pede permissão para acessar a rede local — porque o site
// está mesmo tentando falar com a máquina da pessoa. Nada disso aparece no
// build, nos testes, nas outras guardas nem num `curl`: a página é HTML válido,
// a string é uma string válida, e no computador de quem desenvolve o endereço
// existe de verdade.
//
// Rode DEPOIS de `npm run build`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'frontend/dist';

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

if (!existsSync(DIST)) {
  console.log(`FALHA ${DIST} não existe`);
  console.log('   rode `cd frontend && npm run build` antes desta guarda');
  process.exit(1);
}

// Todo .js sob dist/, em qualquer profundidade — o Astro nomeia a pasta de
// assets de formas diferentes conforme a versão, então procurar por extensão é
// mais durável do que fixar `_astro/`.
const jsFiles = [];
const walk = (dir) => {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) walk(caminho);
    else if (nome.endsWith('.js')) jsFiles.push(caminho);
  }
};
walk(DIST);

check('há JavaScript construído para conferir', jsFiles.length > 0,
  'nenhum .js em dist/ — o build produziu o que se esperava?');

const comLocalhost = jsFiles.filter((f) =>
  /localhost:\d+|127\.0\.0\.1:\d+/.test(readFileSync(f, 'utf8'))
);

check('nenhum bundle aponta para localhost', comLocalhost.length === 0,
  comLocalhost.length
    ? `${comLocalhost.join(', ')} — o endereço do backend caiu no fallback de ` +
      'desenvolvimento. Ver o comentário em frontend/src/services/api.js.'
    : '');

// O outro lado da mesma moeda: o endereço de produção tem de estar lá. Um
// bundle sem localhost E sem o backend não fala com ninguém.
const temProducao = jsFiles.some((f) => readFileSync(f, 'utf8').includes('.run.app'));
check('algum bundle aponta para o backend de produção', temProducao,
  'nenhum .js menciona um endereço .run.app');

process.exit(falhou ? 1 : 0);
