// Sem runner de testes no frontend: este script exercita a função pura em Node.
// Rode com: node scripts/check_cited_text.mjs
import { splitByRefs } from '../frontend/src/utils/citedText.js';

let falhou = false;
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok) {
    console.log('   obtido: ', JSON.stringify(got));
    console.log('   esperado:', JSON.stringify(want));
    falhou = true;
  }
};

const r = (position, item) => ({ position, item_number: item, book: 'O Evangelho Segundo o Espiritismo' });

check('sem refs devolve um fragmento só',
  splitByRefs('texto simples', []),
  [{ type: 'text', value: 'texto simples' }]);

check('ref no meio parte em dois',
  splitByRefs('abc def', [r(3, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(3, '3') }, { type: 'text', value: ' def' }]);

check('ref no fim não gera fragmento vazio',
  splitByRefs('abc', [r(3, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(3, '3') }]);

// O caso que a ordem de renderização exige: o negrito ANTES da citação.
// splitByRefs corta o texto CRU, com os asteriscos — quem os remove é o
// componente, depois, em cada fragmento.
check('negrito antes da citação não desloca o corte',
  splitByRefs('**Kardec** escreve isso', [r(23, '3')]),
  [{ type: 'text', value: '**Kardec** escreve isso' }, { type: 'ref', ref: r(23, '3') }]);

check('refs fora de ordem são ordenadas',
  splitByRefs('abcdef', [r(6, '9'), r(3, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(3, '3') },
   { type: 'text', value: 'def' }, { type: 'ref', ref: r(6, '9') }]);

check('posição além do fim é presa ao fim',
  splitByRefs('abc', [r(999, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(999, '3') }]);

check('texto vazio não quebra', splitByRefs('', [r(0, '3')]), [{ type: 'ref', ref: r(0, '3') }]);

process.exit(falhou ? 1 : 0);
