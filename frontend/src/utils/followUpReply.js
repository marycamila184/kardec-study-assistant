/**
 * Uma resposta de acompanhamento é diálogo, não um card de estudo novo.
 *
 * "Explicar mais simples" e "Como aplicar" montam a pergunta citando o trecho
 * do passo. O backend reconhece o item nessa citação e devolve `studied_item`
 * — corretamente, porque para o /chat isolado essa é a resposta certa. Só que
 * aqui o leitor já tem a passagem na tela, logo acima, no card do passo: o
 * bloco "Da Obra" apareceria duas vezes seguidas, com o mesmo texto.
 *
 * Medido em 2026-07-29 contra o servidor: as duas perguntas devolvem
 * `studied_item` = O Livro dos Espíritos, DE DEUS, item 1, que é exatamente o
 * item do card. O que a leitora pediu foi "somente o diálogo".
 *
 * Devolve uma cópia. O mesmo objeto de resposta alimenta o card do passo em
 * outro ponto da árvore, e mutá-lo apagaria a passagem de lá também.
 */
export function asFollowUp(reply) {
  return { ...reply, hasDaObra: false, obra: null };
}
