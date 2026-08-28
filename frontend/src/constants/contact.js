// Public contact channel. A Google form rather than an email address: no
// address is exposed on the page, and the replies land in her Drive.
//
// Without the `?usp=publish-editor` Google appends when the link is copied from
// inside the editor: that suffix is editing context, not part of the public
// link. Checked 2026-07-27 — opens without a login and does not collect the
// respondent's email automatically.
export const CONTACT_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSf1d5lIjIkwgtABM6P6VuSzraeafEd9uhxtDUERYf4feV61fQ/viewform';

// The logging notice.
//
// Rewritten 2026-07-28: the previous wording promised "não guardamos o
// histórico da conversa", which stopped being true for readers who opt in —
// their turns are linked by a session id for as long as the tab is open. A
// privacy notice describing the previous behaviour is worse than none, so this
// text names the linking and ties it to the reader's authorisation.
//
// It deliberately says LESS than the app does: direct identifiers (e-mail,
// phone, CPF, CEP) are scrubbed before writing, and turns marked `crise` or
// `abalo` record no text at all — neither is mentioned. That asymmetry is the
// safe one and is the standing rule for this file: promising less than you do
// costs nothing, promising more is a false statement about someone's data.
// Anyone tightening what the code does may edit freely here; anyone loosening
// it must check this text first.
export const PRIVACY_NOTICE =
  'Guardo as conversas de forma anônima, só para entender o que precisa ' +
  'melhorar. Não fica nada que identifique você. Se você autorizar, as ' +
  'perguntas de uma mesma conversa ficam ligadas entre si enquanto a aba ' +
  'estiver aberta; isso ajuda quando uma resposta ruim só faz sentido junto ' +
  'com o que veio antes. Depois de 12 meses as mensagens serão apagadas. ' +
  'Se você ligar o lembrete diário, guardo o endereço de notificação do seu ' +
  'aparelho e a hora que você escolheu — só isso, separado das conversas e ' +
  'sem ligação com elas. Some quando você desliga o lembrete, quando o ' +
  'aparelho deixa de existir, ou depois de 90 dias sem uso.';

export const LOCAL_STORAGE_NOTICE =
  'Suas conversas ficam salvas apenas no seu navegador.';

// Vercel's traffic metrics: page, country, device. No cookies and no
// identification — but it is collection that did not exist before, and the
// privacy section would stop being complete without saying so.
export const ANALYTICS_NOTICE =
  'Também medimos acessos de forma agregada (página, país, tipo de aparelho), ' +
  'sem cookies e sem ligar isso às suas conversas.';

// Vai impresso na imagem compartilhada: sem ele, quem recebe o trecho gosta e
// nao tem como chegar ao app. Passou a ser o domínio próprio em 2026-08-04,
// quando ele entrou no ar — a URL da Vercel continua servindo o app, mas não é
// a que se mostra a ninguém.
export const APP_URL = 'dialogandodoutrina.com.br';
