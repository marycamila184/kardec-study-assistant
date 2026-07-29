// O consentimento e o id de sessão vivem em armazenamentos diferentes, e a
// separação é o desenho, não um detalhe:
//
//   a escolha    → localStorage    → dura até a pessoa mudar de ideia
//   o session_id → sessionStorage  → morre quando a aba fecha
//
// A escolha persiste porque não é um identificador: é o mesmo valor para toda
// pessoa que aceitou, não vincula nada a ninguém, e esquecê-la só produziria um
// banner repetido a cada visita — incômodo que não compra privacidade nenhuma.
// O que protege a pessoa é o id morrer, não a preferência dela ser esquecida.
//
// localStorage e não cookie: um cookie é enviado ao servidor automaticamente em
// toda requisição, e o desenho inteiro se apoia em o backend só conhecer a
// sessão pelo header explícito. localStorage nunca sai do navegador a não ser
// que o JS o envie.
//
// Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md

const CHOICE_KEY = 'kardec.logging-consent';
const SESSION_KEY = 'kardec.session-id';

// Navegação privada, storage cheio ou bloqueado por política não podem derrubar
// o app. Sem armazenamento, a resposta é sempre "não consentiu" — o lado seguro.
function safe(fn, fallback = null) {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

// Alguns navegadores antigos só expõem randomUUID em contexto seguro.
function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function hasAnswered() {
  return safe(() => localStorage.getItem(CHOICE_KEY) !== null, false);
}

export function hasConsent() {
  return safe(() => localStorage.getItem(CHOICE_KEY) === 'granted', false);
}

export function grantConsent() {
  safe(() => {
    localStorage.setItem(CHOICE_KEY, 'granted');
    // Um id novo a cada consentimento. Voltar a aceitar nunca ressuscita o id
    // anterior: isso costuraria a sessão de antes da revogação com a de depois,
    // que é exatamente o que revogar deveria ter cortado.
    sessionStorage.setItem(SESSION_KEY, uuid());
  });
}

export function revokeConsent() {
  safe(() => {
    localStorage.setItem(CHOICE_KEY, 'refused');
    sessionStorage.removeItem(SESSION_KEY);
  });
}

// O id da aba atual, ou null quando não há consentimento. É a única fonte do
// header: se isto devolve null, o header não é enviado — e, do lado do
// servidor, a ausência do header É a recusa.
export function sessionId() {
  if (!hasConsent()) return null;
  return safe(() => {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      // Aceitou numa aba anterior e abriu uma nova: a escolha sobreviveu, o id
      // não. Nasce um id novo — a sessão é a aba, não a pessoa.
      id = uuid();
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  });
}
