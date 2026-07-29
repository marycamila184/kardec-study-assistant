// Public contact channel. A Google form rather than an email address: no
// address is exposed on the page, and the replies land in her Drive.
//
// Without the `?usp=publish-editor` Google appends when the link is copied from
// inside the editor: that suffix is editing context, not part of the public
// link. Checked 2026-07-27 — opens without a login and does not collect the
// respondent's email automatically.
export const CONTACT_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSf1d5lIjIkwgtABM6P6VuSzraeafEd9uhxtDUERYf4feV61fQ/viewform';

// The logging notice. "may be recorded", not "are": on crisis and abalo turns
// the text is not logged at all, by design — promising less than you do is
// safe, promising more is not.
//
// Rewritten 2026-07-28: the previous wording promised "não guardamos o
// histórico da conversa", which stopped being true for readers who opt in —
// their turns are linked by a session id for as long as the tab is open. A
// privacy notice describing the previous behaviour is worse than none, so this
// text now names both regimes and which one the reader is in.
export const PRIVACY_NOTICE =
  'Guardo as conversas de forma anônima, só para entender o que precisa ' +
  'melhorar. Não fica nada que identifique você — nem nome, nem IP, nem ' +
  'cookie —, e e-mails, telefones, CPFs e CEPs digitados são apagados antes. ' +
  'Se você autorizar, as perguntas de uma mesma conversa ficam ligadas entre ' +
  'si enquanto a aba estiver aberta; isso ajuda quando uma resposta ruim só ' +
  'faz sentido junto com o que veio antes. Momentos de sofrimento nunca têm o ' +
  'texto guardado, autorizado ou não. Depois de 12 meses, apago.';

export const LOCAL_STORAGE_NOTICE =
  'Suas conversas ficam salvas apenas no seu navegador.';

// Vercel's traffic metrics: page, country, device. No cookies and no
// identification — but it is collection that did not exist before, and the
// privacy section would stop being complete without saying so.
export const ANALYTICS_NOTICE =
  'Também medimos acessos de forma agregada (página, país, tipo de aparelho), ' +
  'sem cookies e sem ligar isso às suas conversas.';

// Vai impresso na imagem compartilhada: sem ele, quem recebe o trecho gosta e
// nao tem como chegar ao app.
export const APP_URL = 'kardec-study-assistant.vercel.app';
