import React from 'react';

/** Renders **bold** markers as <strong>; everything else passes through as plain text. */
export function renderInlineMarkdown(text) {
  if (!text) return text;
  return text.split(/(\*\*[^*]+?\*\*)/g).map((part, i) => {
    const match = part.match(/^\*\*([^*]+?)\*\*$/);
    return match ? <strong key={i}>{match[1]}</strong> : part;
  });
}
