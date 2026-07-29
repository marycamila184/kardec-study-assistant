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
