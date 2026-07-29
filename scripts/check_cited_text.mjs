// Sem runner de testes no frontend: este script exercita a função pura em Node.
// Rode com: node scripts/check_cited_text.mjs
import { splitByRefs, passageKey, citationLabel } from '../frontend/src/utils/citedText.js';

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
// componente, depois, em cada fragmento. Uma implementação que "corrigisse" a
// posição por causa dos ** cairia 4 caracteres antes, e é isso que estes dois
// casos pegam. Uma posição no FIM do texto não pegaria: ali as duas
// implementações coincidem.
check('corte logo depois do negrito respeita os asteriscos',
  splitByRefs('**Kardec** escreve isso', [r(10, '3')]),
  [{ type: 'text', value: '**Kardec**' }, { type: 'ref', ref: r(10, '3') },
   { type: 'text', value: ' escreve isso' }]);

check('corte no meio da frase, com negrito antes',
  splitByRefs('**Kardec** escreve isso', [r(21, '3')]),
  [{ type: 'text', value: '**Kardec** escreve is' }, { type: 'ref', ref: r(21, '3') },
   { type: 'text', value: 'so' }]);

check('duas refs na mesma posição não geram fragmento vazio',
  splitByRefs('abcdef', [r(3, '3'), r(3, '9')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(3, '3') },
   { type: 'ref', ref: r(3, '9') }, { type: 'text', value: 'def' }]);

check('refs fora de ordem são ordenadas',
  splitByRefs('abcdef', [r(6, '9'), r(3, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(3, '3') },
   { type: 'text', value: 'def' }, { type: 'ref', ref: r(6, '9') }]);

check('posição além do fim é presa ao fim',
  splitByRefs('abc', [r(999, '3')]),
  [{ type: 'text', value: 'abc' }, { type: 'ref', ref: r(999, '3') }]);

check('texto vazio não quebra', splitByRefs('', [r(0, '3')]), [{ type: 'ref', ref: r(0, '3') }]);

// passageKey — a identidade usada para tirar da fileira de chips o que já
// virou link inline. O capítulo faz parte da chave porque a numeração reinicia
// por capítulo em A Gênese, Evangelho e Céu e Inferno.
const generseCapI = passageKey({
  book: 'A Gênese', chapter_ref: 'CAPÍTULO I', item_number: '3',
});
const generseCapII = passageKey({
  book: 'A Gênese', chapter_ref: 'CAPÍTULO II', item_number: '3',
});
check('passageKey: mesmo item, capítulos diferentes de A Gênese → chaves diferentes',
  generseCapI === generseCapII, false);

check('passageKey: item_number "section-3" nunca filtra',
  passageKey({ book: 'X', chapter_ref: null, item_number: 'section-3' }), null);

check('passageKey: item_number null nunca filtra',
  passageKey({ book: 'X', chapter_ref: null, item_number: null }), null);

// citationLabel — o rótulo do link inline.
check('citationLabel: short dentro de um capítulo conhecido → "item N"',
  citationLabel(
    { book: 'O Evangelho Segundo o Espiritismo', chapter_ref: 'CAPÍTULO XII', item_number: '3' },
    'short', true,
  ),
  'item 3');

// Não fixado numa string exata: sobrevive a um ajuste de formatação em
// format.js, desde que o rótulo continue nomeando obra e capítulo.
const shortForaDoCapitulo = citationLabel(
  { book: 'O Evangelho Segundo o Espiritismo', chapter_ref: 'CAPÍTULO XII', item_number: '3' },
  'short', false,
);
check('citationLabel: short fora de um capítulo conhecido nomeia a obra',
  shortForaDoCapitulo.includes('O Evangelho Segundo o Espiritismo'), true);
check('citationLabel: short fora de um capítulo conhecido nomeia o capítulo',
  shortForaDoCapitulo.includes('XII'), true);

const full = citationLabel(
  { book: 'O Evangelho Segundo o Espiritismo', chapter_ref: 'CAPÍTULO XII', item_number: '3' },
  'full', true,
);
check('citationLabel: full nomeia a obra', full.includes('O Evangelho Segundo o Espiritismo'), true);
check('citationLabel: full nomeia o capítulo', full.includes('XII'), true);
check('citationLabel: full nomeia o item', full.includes('3'), true);

process.exit(falhou ? 1 : 0);
