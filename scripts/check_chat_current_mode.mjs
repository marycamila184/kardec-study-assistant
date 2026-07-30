// Sem runner de testes no frontend: este script lê App.jsx e confere os call
// sites. Rode com: node scripts/check_chat_current_mode.mjs
//
// O que ele guarda: toda chamada a /chat tem de declarar `current_mode`.
// O orchestrator nunca sugere o modo em que o leitor já está — mas ele só
// consegue aplicar essa regra se souber qual é o modo, e `current_mode` é o
// único jeito de contar. Omitir o argumento manda `undefined` e reabilita o
// auto-nudge em silêncio: o leitor dentro de Estudar recebe "📖 Estudar Q.920
// na íntegra" para a passagem que já está lendo.
//
// Isto não é hipotético. As duas portas do Explorar foram corrigidas em algum
// momento e outras três ficaram para trás — "Explicar simples", "Tenho uma
// dúvida" e o fallback 404 de handleAskTopic. Um comentário no código já
// avisava da armadilha e mesmo assim ela reapareceu, que é exatamente o tipo
// de regressão que merece uma checagem automática em vez de vigilância.
//
// A posição importa: em chatMessage(question, history, bookFilter, currentMode,
// profile) e em chatMessageStream(question, history, bookFilter, currentMode,
// onToken, profile) o modo é o 4º argumento nas duas.
import { readFileSync } from 'node:fs';

const FILE = 'frontend/src/App.jsx';
const MODE_ARG_INDEX = 3; // 0-based: o 4º argumento
const src = readFileSync(FILE, 'utf-8');

// Varre caractere a caractere sabendo em que string está. As aspas e a crase
// são simétricas — o mesmo caractere abre e fecha — então contá-las como
// profundidade nunca volta a zero. Foi o que a primeira versão fez, e ela
// acusou como "sem current_mode" a chamada do trecho do dia, cujo template
// literal carrega `slice(0, 300)`: parênteses e vírgula dentro de uma string.
// Um checador que inventa uma falha é pior que checador nenhum.
function* scan(text, from) {
  let quote = null; // "'", '"' ou '`'
  for (let i = from; i < text.length; i++) {
    const ch = text[i];
    const prev = text[i - 1];
    if (quote) {
      if (ch === quote && prev !== '\\') quote = null;
      yield { i, ch, inString: true };
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      quote = ch;
      yield { i, ch, inString: true };
      continue;
    }
    yield { i, ch, inString: false };
  }
}

function argsAt(text, openParen) {
  let depth = 0;
  for (const { i, ch, inString } of scan(text, openParen)) {
    if (inString) continue;
    if (ch === '(') depth++;
    else if (ch === ')') {
      depth--;
      if (depth === 0) return text.slice(openParen + 1, i);
    }
  }
  return null;
}

function splitTopLevel(args) {
  const out = [];
  let depth = 0;
  let current = '';
  for (const { ch, inString } of scan(args, 0)) {
    if (!inString) {
      if ('([{'.includes(ch)) depth++;
      else if (')]}'.includes(ch)) depth--;
      if (ch === ',' && depth === 0) {
        out.push(current.trim());
        current = '';
        continue;
      }
    }
    current += ch;
  }
  if (current.trim()) out.push(current.trim());
  return out;
}

const lineOf = (index) => src.slice(0, index).split('\n').length;

let falhou = false;
const found = [];

for (const name of ['chatMessage', 'chatMessageStream']) {
  const re = new RegExp(`(?<![\\w.])${name}\\s*\\(`, 'g');
  let m;
  while ((m = re.exec(src)) !== null) {
    const line = lineOf(m.index);
    // Linhas comentadas descrevem o código antigo, não chamam nada.
    const lineText = src.split('\n')[line - 1];
    if (lineText.trimStart().startsWith('//')) continue;
    const args = argsAt(src, m.index + m[0].length - 1);
    if (args === null) continue;
    const parts = splitTopLevel(args);
    const mode = parts[MODE_ARG_INDEX];
    found.push({ name, line, nargs: parts.length, mode });
  }
}

console.log(`${found.length} chamadas a /chat em ${FILE}\n`);
for (const c of found) {
  const ok = c.mode !== undefined;
  if (!ok) falhou = true;
  const shown = c.mode === undefined ? '(AUSENTE)' : c.mode;
  console.log(`${ok ? 'OK   ' : 'FALHA'} L${c.line} ${c.name} — ${c.nargs} args, current_mode=${shown}`);
}

if (falhou) {
  console.log(
    '\nUma chamada sem current_mode manda undefined e o orchestrator volta a\n' +
    'sugerir o modo em que o leitor já está. Passe o modo da tela:\n' +
    "  'estudar_obra' dentro de Estudar (Explorar, trilhas, quick actions)\n" +
    "  'tirar_duvida' na thread principal\n" +
    '  null explicitamente quando o nudge DEVE aparecer (o trecho do dia).',
  );
  process.exit(1);
}
console.log('\nTodas as chamadas declaram current_mode.');
