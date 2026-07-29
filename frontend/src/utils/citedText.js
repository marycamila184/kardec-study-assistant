import { formatItemRef, formatSourceRef } from './format.js';

// Corta o texto nas posições das referências inline.
//
// Opera no texto CRU, com os `**` do negrito ainda presentes: as posições vêm
// do backend contadas assim. Quem transforma markdown é quem consome esta
// função, fragmento a fragmento — inverter a ordem desloca cada link em 4
// caracteres por negrito anterior, silenciosamente.
//
// Ver docs/superpowers/specs/2026-07-29-citacao-inline-clicavel-design.md
export function splitByRefs(text, refs) {
  const source = text || '';
  if (!refs || refs.length === 0) return [{ type: 'text', value: source }];

  const ordered = [...refs].sort((a, b) => a.position - b.position);
  const out = [];
  let last = 0;

  for (const ref of ordered) {
    // Presa ao fim: uma posição além do texto viria de um desencontro entre o
    // que o backend contou e o que o cliente recebeu, e nesse caso o link no
    // fim é melhor do que um fragmento perdido.
    const at = Math.max(last, Math.min(ref.position ?? 0, source.length));
    if (at > last) out.push({ type: 'text', value: source.slice(last, at) });
    out.push({ type: 'ref', ref });
    last = at;
  }

  if (last < source.length) out.push({ type: 'text', value: source.slice(last) });
  return out;
}

// Identity of a passage, for matching an inline citation against a chip.
//
// The chapter is part of it: item numbers restart every chapter in O Evangelho
// Segundo o Espiritismo, O Céu e o Inferno and A Gênese, so book+item alone
// collapses two different passages into one key — and /chat retrieval is not
// chapter-scoped. The backend keeps them apart for the same reason.
//
// A passage with no real item number (the parser's "section-N" placeholders,
// which reach one side raw and the other as null) gets NO key and is never
// filtered. That asymmetry is chosen: showing a chip twice is untidy, while
// dropping a passage the answer actually used is the failure this whole
// feature exists to prevent.
export const passageKey = (p) => {
  const item = String(p.item_number ?? '');
  if (!/^\d+$/.test(item)) return null;
  return `${p.book}|${p.chapter_ref ?? ''}|${item}`;
};

// O rótulo do link.
//
// `full` traz a forma canônica inteira. `short` traz a MENOR referência que
// continua sem ambiguidade onde o leitor está: no estudo o capítulo já está na
// tela, no bloco "Da Obra", então o número basta; no chat a busca cruza obras,
// e um link dizendo só "item 3" não identifica nada.
export function citationLabel(ref, precision, insideOneChapter) {
  if (precision === 'full') {
    return formatSourceRef({
      book: ref.book, chapterRef: ref.chapter_ref, itemNumber: ref.item_number,
    });
  }
  return insideOneChapter
    ? formatItemRef(ref.book, ref.item_number)
    // Not inside one known chapter (chat's cross-book retrieval): the chapter
    // ref must ride along, because O Evangelho, O Céu e o Inferno and A
    // Gênese restart item numbering every chapter — "item 1" alone matches
    // many passages in those books. See format.js's formatSourceRef docstring.
    : formatSourceRef({ book: ref.book, chapterRef: ref.chapter_ref, itemNumber: ref.item_number });
}
