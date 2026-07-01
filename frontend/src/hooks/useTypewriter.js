import { useEffect, useRef, useState } from 'react';

/**
 * Reveals `fullText` progressively, a few characters at a time, keyed off `key`
 * so the same message doesn't re-type on unrelated re-renders.
 *   fullText — the complete string to reveal
 *   options.speed — ms between reveal ticks (default 18)
 *   options.chunkSize — characters revealed per tick (default 2)
 *   options.key — identity that resets the reveal when it changes (e.g. msg.id)
 * Returns the currently-visible substring of fullText.
 */
export function useTypewriter(fullText, { speed = 18, chunkSize = 2, key } = {}) {
  const [visibleLength, setVisibleLength] = useState(0);
  const keyRef = useRef(key);

  useEffect(() => {
    keyRef.current = key;
    setVisibleLength(0);
  }, [key]);

  useEffect(() => {
    if (visibleLength >= (fullText?.length || 0)) return;
    const timer = setTimeout(() => {
      if (keyRef.current !== key) return;
      setVisibleLength(v => Math.min(v + chunkSize, fullText.length));
    }, speed);
    return () => clearTimeout(timer);
  }, [visibleLength, fullText, speed, chunkSize, key]);

  return (fullText || '').slice(0, visibleLength);
}
