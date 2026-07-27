// Canal público de contato. Formulário do Google em vez de e-mail: nenhum
// endereço fica exposto na página, e as respostas caem no Drive dela.
//
// Sem o `?usp=publish-editor` que o Google acrescenta ao copiar de dentro do
// editor: aquele sufixo é contexto de edição, não faz parte do link público.
// Verificado em 2026-07-27 — abre sem login e não coleta e-mail automaticamente.
export const CONTACT_FORM_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLSf1d5lIjIkwgtABM6P6VuSzraeafEd9uhxtDUERYf4feV61fQ/viewform';

// Aviso de registro anônimo. "podem ser registradas", não "são": em turnos de
// crise e abalo o texto não é registrado, por decisão de desenho — prometer
// menos do que se faz é seguro, prometer mais não é.
export const PRIVACY_NOTICE =
  'As conversas podem ser registradas de forma anônima para melhorar as respostas. ' +
  'Nada é associado a você: não guardamos identificação, nem o histórico da conversa.';

export const LOCAL_STORAGE_NOTICE =
  'Suas conversas ficam salvas apenas no seu navegador.';
