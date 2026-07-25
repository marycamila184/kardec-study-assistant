// "Q.N" is O Livro dos Espíritos vocabulary (its entries are questões,
// globally numbered); the other works call their numbered entries itens.
export function formatItemRef(book, itemNumber) {
  return book === 'O Livro dos Espíritos' ? `Q.${itemNumber}` : `item ${itemNumber}`;
}
