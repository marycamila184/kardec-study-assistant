import { splitByRefs } from '../../utils/citedText';
import { renderInlineMarkdown } from '../../utils/inlineMarkdown';
import { formatItemRef, formatSourceRef } from '../../utils/format';

// O rótulo do link.
//
// `full` traz a forma canônica inteira. `short` traz a MENOR referência que
// continua sem ambiguidade onde o leitor está: no estudo o capítulo já está na
// tela, no bloco "Da Obra", então o número basta; no chat a busca cruza obras,
// e um link dizendo só "item 3" não identifica nada.
function label(ref, precision, insideOneChapter) {
  if (precision === 'full') {
    return formatSourceRef({
      book: ref.book, chapterRef: ref.chapter_ref, itemNumber: ref.item_number,
    });
  }
  return insideOneChapter
    ? formatItemRef(ref.book, ref.item_number)
    : formatSourceRef({ book: ref.book, itemNumber: ref.item_number });
}

// O texto da resposta com as citações no lugar em que a afirmação se apoia
// nelas. Sem refs, é exatamente o que era antes.
export default function CitedText({
  text, refs, theme, onOpenSource, precision = 'short', insideOneChapter = false,
}) {
  const parts = splitByRefs(text, refs);

  return (
    <>
      {parts.map((part, i) =>
        part.type === 'text' ? (
          // O markdown é renderizado AQUI, depois do corte — nunca antes.
          <span key={i}>{renderInlineMarkdown(part.value)}</span>
        ) : (
          <button
            key={i}
            onClick={() => onOpenSource(part.ref)}
            title="Ver a passagem"
            style={{
              background: 'none', border: 'none', padding: '0 2px',
              font: 'inherit', fontSize: '0.88em', color: '#6B9BB8',
              textDecoration: 'underline', textUnderlineOffset: 2,
              cursor: 'pointer',
            }}
          >
            {label(part.ref, precision, insideOneChapter)}
          </button>
        )
      )}
    </>
  );
}
