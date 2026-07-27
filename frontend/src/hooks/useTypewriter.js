import { useEffect, useRef, useState } from 'react';

/**
 * Reveals `fullText` progressively, one word at a time, keyed off `key`
 * so the same message doesn't re-type on unrelated re-renders.
 *   fullText — the complete string to reveal
 *   options.speed — ms between reveal ticks (default 50)
 *   options.key — identity that resets the reveal when it changes (e.g. msg.id)
 *   options.start — hold at zero until true, so two reveals can run in
 *     sequence at one speed instead of one appearing whole while the other
 *     types. Defaults to true, which is the single-reveal behaviour.
 * Returns the currently-visible substring of fullText.
 */
export function useTypewriter(fullText, { speed = 50, key, skip = false, start = true } = {}) {
  const full = fullText || '';
  const words = full.match(/\S+\s*/g) || [];
  const [visibleWords, setVisibleWords] = useState(skip ? words.length : 0);
  const keyRef = useRef(key);

  useEffect(() => {
    keyRef.current = key;
    setVisibleWords(skip ? (full.match(/\S+\s*/g) || []).length : 0);
  }, [key, skip]);

  useEffect(() => {
    if (skip || !start || visibleWords >= words.length) return;
    const timer = setTimeout(() => {
      if (keyRef.current !== key) return;
      setVisibleWords(v => Math.min(v + 1, words.length));
    }, speed);
    return () => clearTimeout(timer);
  }, [visibleWords, words.length, speed, key, skip, start]);

  return skip ? full : words.slice(0, visibleWords).join('');
}
