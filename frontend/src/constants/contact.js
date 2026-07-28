// Public contact channel. A Google form rather than an email address: no
// address is exposed on the page, and the replies land in her Drive.
//
// Without the `?usp=publish-editor` Google appends when the link is copied from
// inside the editor: that suffix is editing context, not part of the public
// link. Checked 2026-07-27 — opens without a login and does not collect the
// respondent's email automatically.
export const CONTACT_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSf1d5lIjIkwgtABM6P6VuSzraeafEd9uhxtDUERYf4feV61fQ/viewform';

// The anonymous-logging notice. "may be recorded", not "are": on crisis and
// abalo turns the text is not logged at all, by design — promising less than
// you do is safe, promising more is not.
export const PRIVACY_NOTICE =
  'As conversas podem ser registradas de forma anônima para melhorar as respostas. ' +
  'Nada é associado a você: não guardamos identificação, nem o histórico da conversa.';

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
