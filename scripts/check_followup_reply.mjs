// Sem runner de testes no frontend: este script exercita a função pura em Node.
// Rode com: node scripts/check_followup_reply.mjs
import { asFollowUp } from '../frontend/src/utils/followUpReply.js';

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

// O caso medido em 2026-07-29 contra o servidor: "Como aplicar" e "Explicar
// mais simples" citam o trecho do passo na pergunta, o backend resolve o item
// a partir da citação e devolve `studied_item` — o MESMO item que o card do
// passo já exibe. Sem isto, o bloco "Da Obra" renderiza duas vezes na tela.
const respostaDoBackend = {
  hasDaObra: true,
  obra: { title: 'O Livro dos Espíritos — DE DEUS', quote: '1. Que é Deus? …' },
  ia: 'Kardec escreve que "Deus é a inteligência suprema"…',
  turnId: 'abc',
  suggestedQuestions: ['e o que é o bem?'],
};

check('acompanhamento não repete o bloco Da Obra',
  asFollowUp(respostaDoBackend).hasDaObra,
  false);

check('a passagem some junto com a flag',
  asFollowUp(respostaDoBackend).obra,
  null);

check('a prosa e o resto da resposta passam intactos',
  (({ hasDaObra, obra, ...resto }) => resto)(asFollowUp(respostaDoBackend)),
  (({ hasDaObra, obra, ...resto }) => resto)(respostaDoBackend));

// Não muta: o card do passo continua sendo renderizado a partir do mesmo
// objeto em outro ponto da árvore, e mutá-lo apagaria a passagem de lá também.
asFollowUp(respostaDoBackend);
check('não muta a resposta original', respostaDoBackend.hasDaObra, true);

// Uma resposta que já vem sem passagem não deve ganhar campos.
check('resposta sem Da Obra continua sem', asFollowUp({ ia: 'texto' }).hasDaObra, false);

if (falhou) process.exit(1);
console.log('\nTodos os casos passaram.');
