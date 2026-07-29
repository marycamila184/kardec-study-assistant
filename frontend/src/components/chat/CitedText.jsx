import { splitByRefs, citationLabel } from '../../utils/citedText';
import { renderInlineMarkdown } from '../../utils/inlineMarkdown';

// O texto da resposta com as citações no lugar em que a afirmação se apoia
// nelas. Sem refs, é exatamente o que era antes.
export default function CitedText({
  text, refs, onOpenSource, precision = 'short', insideOneChapter = false,
}) {
  const parts = splitByRefs(text, refs);

  return (
    <>
      {parts.map((part, i) =>
        part.type === 'text' ? (
          // O markdown é renderizado AQUI, depois do corte — nunca antes.
          //
          // Two accepted limits, not overlooked:
          // - A `[fonte N]` marker landing INSIDE a `**bold**` span leaves
          //   literal asterisks on screen — renderInlineMarkdown only matches
          //   a complete `**…**` within one fragment, and the cut can sever
          //   it. Degradation only: the link and the passage stay correct.
          // - `position` is a Python code-point index, consumed here as a
          //   UTF-16 index. The two agree for all BMP text, which is all
          //   Portuguese prose; a non-BMP character (an emoji) before a
          //   marker would shift later links by one. Latent, not live — no
          //   prompt asks for emoji and the two texts that contain them
          //   (crisis exit, small talk) can never carry refs.
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
            {citationLabel(part.ref, precision, insideOneChapter)}
          </button>
        )
      )}
    </>
  );
}
