import { useEffect, useRef, useState } from 'react';

/**
 * Reveals `fullText` progressively, one word at a time, keyed off `key`
 * so the same message doesn't re-type on unrelated re-renders.
 *   fullText — the complete string to reveal
 *   options.speed — ms between reveal ticks (default 50)
 *   options.key — identity that resets the reveal when it changes (e.g. msg.id)
 * Returns the currently-visible substring of fullText.
 */
export function useTypewriter(fullText, { speed = 50, key } = {}) {
  const [visibleWords, setVisibleWords] = useState(0);
  const keyRef = useRef(key);

  // Split keeping the whitespace attached to the following word, so
  // newlines/spacing are preserved exactly when words are re-joined.
  const words = (fullText || '').match(/\S+\s*/g) || [];

  useEffect(() => {
    keyRef.current = key;
    setVisibleWords(0);
  }, [key]);

  useEffect(() => {
    if (visibleWords >= words.length) return;
    const timer = setTimeout(() => {
      if (keyRef.current !== key) return;
      setVisibleWords(v => Math.min(v + 1, words.length));
    }, speed);
    return () => clearTimeout(timer);
  }, [visibleWords, words.length, speed, key]);

  return words.slice(0, visibleWords).join('');
}
