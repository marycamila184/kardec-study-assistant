// Confere que o banner de consentimento continua sendo perguntado onde deve, e
// só onde deve.
//
// O consentimento sobe na primeira vez que a pessoa pede alguma coisa por
// vontade própria. São CINCO pontos de entrada em App.jsx, e cinco chamadas
// iguais espalhadas por um arquivo de 1450 linhas é a forma exata do bug que
// este repositório já pagou: `current_mode` foi corrigido em dois pontos e três
// ficaram para trás, e a resposta foi scripts/check_chat_current_mode.mjs.
//
// A falha aqui é silenciosa por natureza: um handler que esquece a chamada
// continua funcionando perfeitamente — a resposta chega, a tela pinta — e a
// pessoa simplesmente nunca é perguntada. Nada no app em execução mostraria
// isso, e o resultado é uma escolha que nunca foi oferecida.
//
// O outro sentido importa igual: os turnos que o APP gera não podem perguntar.
// Chegar numa trilha, abrir o trecho do dia ou seguir um deep link é leitura, e
// pedir consentimento por cima de um texto que a pessoa ainda não leu foi
// exatamente o que motivou esta mudança (medido em produção, 2026-08-10).
import { readFileSync } from 'node:fs';

const APP = 'frontend/src/App.jsx';
const MARCA = 'markReaderAsked()';

// Iniciados pela pessoa: têm de chamar.
const PEDE = [
  'sendText',            // a caixa de Dialogar
  'runQuickAction',      // as três ações rápidas
  'askDuvida',           // os chips de seguimento (GuidedStudy não tem caixa de texto)
  'handleAskTopic',      // os chips de tema do estudo livre
  'handleExplorarChat',  // o que é digitado no estudo livre
];

// Gerados pelo app: NÃO podem chamar.
const NAO_PEDE = [
  'presentGuidedStep',   // um passo da trilha
  'handleStudyTrecho',   // o turno automático do trecho do dia
  'handleGoStudyItem',   // um deep link vindo de uma página estática
];

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

// Tira comentários de linha e de bloco antes de qualquer busca. Achado em
// revisão (2026-08-10): `corpo()` cortava em `\n  const `, e um bloco morto
// comentado — `handleGoReflect`, entre `handleGoStudyItem` e
// `handleLoadConvo` — não começa com `const` porque o `//` vem antes, então a
// varredura andava direto por cima dele. Hoje isso dá o veredito certo por
// sorte (o bloco morto não contém `markReaderAsked()`), mas reabilitar aquele
// código — ou qualquer edição nele — vira um CI vermelho por um motivo que
// não tem nada a ver com a função sob teste; e o inverso também é
// construível: uma função obrigatória perde a chamada e o texto varrido
// depois dela contém `markReaderAsked()` por acaso, e a guarda aprova errado.
// Uma guarda que existe porque a falha é silenciosa não pode ela mesma dar um
// veredito pelo motivo errado. String/template literals são preservados —
// só o comentário em si é removido — porque não há razão para simplificar
// mais que isso.
const semComentarios = (src) => {
  let out = '';
  let i = 0;
  let linha = false, bloco = false, simples = false, dupla = false, template = false;
  while (i < src.length) {
    const c = src[i];
    const c2 = src[i + 1];
    if (linha) {
      if (c === '\n') { linha = false; out += c; }
      i++; continue;
    }
    if (bloco) {
      if (c === '*' && c2 === '/') { bloco = false; i += 2; continue; }
      i++; continue;
    }
    if (simples || dupla || template) {
      out += c;
      if (c === '\\') { out += src[i + 1] ?? ''; i += 2; continue; }
      if ((simples && c === "'") || (dupla && c === '"') || (template && c === '`')) {
        simples = dupla = template = false;
      }
      i++; continue;
    }
    if (c === '/' && c2 === '/') { linha = true; i += 2; continue; }
    if (c === '/' && c2 === '*') { bloco = true; i += 2; continue; }
    if (c === "'") { simples = true; out += c; i++; continue; }
    if (c === '"') { dupla = true; out += c; i++; continue; }
    if (c === '`') { template = true; out += c; i++; continue; }
    out += c; i++;
  }
  return out;
};

const app = semComentarios(readFileSync(APP, 'utf8'));

check(`${APP} declara ${MARCA.replace('()', '')}`, app.includes(`const markReaderAsked =`));
check('o banner recebe show={readerAsked}', /<ConsentBanner[^>]*show=\{readerAsked\}/.test(app));

// O corpo de cada função: do `const <nome> = ` até o próximo `\n  const ` no
// mesmo nível de indentação, já sem comentários (ver semComentarios acima).
// Grosseiro de propósito — a alternativa é um parser, e o que se quer saber é
// só se a chamada está lá dentro.
const corpo = (nome) => {
  const inicio = app.indexOf(`const ${nome} = `);
  if (inicio === -1) return null;
  const resto = app.slice(inicio + 1);
  const fim = resto.indexOf('\n  const ');
  return fim === -1 ? resto : resto.slice(0, fim);
};

for (const nome of PEDE) {
  const c = corpo(nome);
  check(`${nome} existe em ${APP}`, c !== null,
    'renomeada? esta guarda casa por nome — atualize a lista junto com o código');
  if (c) {
    check(`${nome} pede o consentimento`, c.includes(MARCA),
      'a pessoa pediu alguma coisa e nunca seria perguntada');
  }
}

for (const nome of NAO_PEDE) {
  const c = corpo(nome);
  check(`${nome} existe em ${APP}`, c !== null,
    'renomeada? esta guarda casa por nome — atualize a lista junto com o código');
  if (c) {
    check(`${nome} NÃO pede o consentimento`, !c.includes(MARCA),
      'é um turno gerado pelo app: pedir aqui sobe o banner por cima de quem só está lendo');
  }
}

process.exit(falhou ? 1 : 0);
